from app.wraps import wrap_hitbtc, wrap_bittrex, wrap_binance, wrap_poloniex, wrap_p2pb2b
import json
import os
from app.settings import DB_HOST_JOBQUEUE, DB_NAME_JOBQUEUE, DB_PORT_JOBQUEUE, EXCHANGES
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid
from app.lib.jobqueue import JOB_COLLECTION
from app.lib.common import get_coingecko_meta, get_current_fiat_rate, dynamically_import_exchange
from app.lib.db import store_fiat_rates
import random

MARKETS_JSON = "/app/markets.json"
FIAT_RATES_JSON = "/app/fiat_rates.json"


def setup_database():
    dbclient = MongoClient(host=DB_HOST_JOBQUEUE, port=DB_PORT_JOBQUEUE)
    # creates the database if it doesn't already exist
    db = dbclient[DB_NAME_JOBQUEUE]
    try:
        db.create_collection(JOB_COLLECTION)
    except CollectionInvalid:
        pass
    assert (DB_NAME_JOBQUEUE in dbclient.list_database_names())


def setup_currency_pairs():
    apis = get_exchanges()
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
    markets_location = ''.join([os.getcwd(), MARKETS_JSON])
    with open(markets_location, 'w') as outfile:
        json.dump(data, outfile, indent=2)


def load_currency_pairs():
    markets_location = ''.join([os.getcwd(), MARKETS_JSON])
    if not os.path.isfile(markets_location):
        raise FileExistsError(
            'Run the command again and specify --setup to create the list of markets at {}'.format(markets_location))
    with open(markets_location) as data_file:
        result = json.loads(data_file.read())
    return result


def get_exchanges():
    # instantiate each of the api wrappers
    exchanges = []
    for exchange in EXCHANGES:
        # add the instantiated exchange client to a list of clients, e.g. wrap_binance.binance()
        exchanges.append(dynamically_import_exchange(exchange)())

    return exchanges


# take all of the exchanges and choose two of them
def choose_two_random_exchanges():
    try:
        exchanges = []
        total_exchanges = len(EXCHANGES)
        random_indexes = []
        while len(exchanges) != 2:
            random_index = random.randint(0, total_exchanges - 1)
            if random_index not in random_indexes:
                random_indexes.append(random_index)
                # add the instantiated exchange client to a list of clients, e.g. wrap_binance.binance()
                exchanges.append(dynamically_import_exchange(EXCHANGES[random_index])())
    except Exception as e:
        raise SetupError('Error randomly selecting exchanges for comparison: {}'.format(e))
    return exchanges


def setup_environment():
    setup_currency_pairs()
    setup_database()
    get_coingecko_meta()
    update_fiat_rates()


def update_fiat_rates():
    btc_rate = get_current_fiat_rate('BTC')
    eth_rate = get_current_fiat_rate('ETH')
    fiat_rates = {'BTC': btc_rate, 'ETH': eth_rate}
    store_fiat_rates(fiat_rates)


class SetupError(Exception):
    pass