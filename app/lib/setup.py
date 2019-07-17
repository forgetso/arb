import json
import os
from app.settings import DB_HOST, DB_NAME_JOBQUEUE, DB_PORT_JOBQUEUE, EXCHANGES, TRADE_PAIRS, MASTER_EXCHANGE
from pymongo import MongoClient, version_tuple as pymongo_version_tuple
from pymongo.errors import CollectionInvalid
from app.lib.jobqueue import JOB_COLLECTION
from app.lib.common import dynamically_import_exchange
from app.lib.coingecko import get_coingecko_meta, get_current_fiat_rates
from app.lib.db import store_fiat_rates
import random
from pathlib import Path

MARKETS_JSON = "/markets.json"
FIAT_RATES_JSON = "/app/fiat_rates.json"


def setup_database():
    dbclient = MongoClient(host=DB_HOST, port=DB_PORT_JOBQUEUE)
    # creates the database if it doesn't already exist
    db = dbclient[DB_NAME_JOBQUEUE]
    try:
        db.create_collection(JOB_COLLECTION)
    except CollectionInvalid:
        pass
    # list database names does not exist in pymongo3.4, which we're using on raspberry pi
    if pymongo_version_tuple[0] <= 3 and pymongo_version_tuple[1] < 6:
        assert (DB_NAME_JOBQUEUE in dbclient.database_names())
    else:
        assert (DB_NAME_JOBQUEUE in dbclient.list_database_names())


def setup_currency_pairs(jobqueue_id):
    apis = get_exchanges(jobqueue_id)
    currency_pair_symbols = set()
    currency_pairs_result = {}
    for api in apis:
        currency_pairs_result.setdefault(api.name, {})
        api_currency_pairs = api.get_currency_pairs()
        for currency_pair in api_currency_pairs:
            if (currency_pair['base_currency'], currency_pair['quote_currency']) in currency_pair_symbols:
                currency_pairs_result[api.name][currency_pair['name']] = currency_pair
                continue
            if (currency_pair['quote_currency'], currency_pair['base_currency']) in currency_pair_symbols:
                code_list = currency_pair['name'].split('-')
                reverse_trading_code = '-'.join(code_list)
                currency_pairs_result[api.name][reverse_trading_code] = currency_pair
                continue

            currency_pairs_result[api.name][currency_pair['name']] = currency_pair
            currency_pair_symbols |= set((tuple([currency_pair['base_currency'], currency_pair['quote_currency']]),))

    write_currency_pairs(currency_pairs_result)
    return currency_pairs_result


def write_currency_pairs(data):
    path = Path(__file__).parent.parent
    markets_location = ''.join([str(path), MARKETS_JSON])
    with open(markets_location, 'w') as outfile:
        json.dump(data, outfile, indent=2)


def load_currency_pairs():
    path = Path(__file__).parent.parent
    markets_location = ''.join([str(path), MARKETS_JSON])
    if not os.path.isfile(markets_location):
        raise FileExistsError(
            'Run the command again and specify --setup to create the list of markets at {}'.format(markets_location))
    with open(markets_location) as data_file:
        result = json.loads(data_file.read())
    return result


def get_exchanges(jobqueue_id):
    # instantiate each of the api wrappers
    exchanges = []
    for exchange in EXCHANGES:
        # add the instantiated exchange client to a list of clients, e.g. wrap_binance.binance()
        exchanges.append(dynamically_import_exchange(exchange)(jobqueue_id))

    return exchanges


def get_master_exchange(jobqueue_id):
    # there is no restriction on importing the master exchange as it is always required to fund exchanges
    # even if it is not being used to trade
    return dynamically_import_exchange(MASTER_EXCHANGE)(jobqueue_id)


def get_exchange(exchange, jobqueue_id):
    if exchange in EXCHANGES or exchange != MASTER_EXCHANGE:
        return dynamically_import_exchange(exchange)(jobqueue_id)
    else:
        raise ValueError('Exchange {} is not currently being used'.format(exchange))


# take all of the exchanges and choose two of them
def choose_random_exchanges(number=2, potential_exchanges=None, duplicates=False):
    if not potential_exchanges:
        potential_exchanges = EXCHANGES
    try:
        exchanges = []
        total_exchanges = len(potential_exchanges)
        random_indexes = []
        while len(exchanges) != number:
            random_index = random.randint(0, total_exchanges - 1)
            if (random_index not in random_indexes) or duplicates:
                random_indexes.append(random_index)
                # add the instantiated exchange client to a list of clients, e.g. wrap_binance.binance()
                exchanges.append(potential_exchanges[random_index])
    except Exception as e:
        raise SetupError('Error randomly selecting exchanges for comparison: {}'.format(e))
    return exchanges

def setup_environment(jobqueue_id):
    setup_currency_pairs(jobqueue_id=jobqueue_id)
    setup_database()
    get_coingecko_meta()
    update_fiat_rates()


def update_fiat_rates():
    currencies = []
    fiat_rates = {}
    for trade_pair in TRADE_PAIRS:
        cur_x, cur_y = trade_pair.split('-')
        currencies.append(cur_x)
        currencies.append(cur_y)
    currencies_set = set(currencies)
    fiat_rates = get_current_fiat_rates(currencies_set)

    store_fiat_rates(fiat_rates)


class SetupError(Exception):
    pass
