from web.settings import FIAT_REPLENISH_AMOUNT, FIAT_DEFAULT_SYMBOL
from math import modf
from decimal import Decimal
import os, json, requests

COINGECKO_META = "/web/coingecko_meta.json"


def get_replenish_quantity(currency):
    fiat_rate = get_current_fiat_rate(crypto_symbol=currency, fiat_symbol=FIAT_DEFAULT_SYMBOL)
    try:
        quantity = FIAT_REPLENISH_AMOUNT / fiat_rate
    except Exception as e:
        raise CommonError('Error getting replenish quantity {}'.format(e))

    return quantity


def get_number_of_decimal_places(number):
    try:
        # takes the decimal part of the minimum trade size and inverts it, giving the number of decimal places
        decimal_places = round(1 / modf(number)[0])
    except Exception as e:
        raise CommonError('Error getting decimal places {}'.format(e))
    return decimal_places


def round_decimal_number(number, decimal_places):
    # rounds the volume to the correct number of decimal places
    number_corrected = number.quantize(Decimal('1.{}'.format(decimal_places * '0')))
    return number_corrected


def get_current_fiat_rate(crypto_symbol, fiat_symbol=None):
    crypto_symbol = crypto_symbol.lower()
    try:
        if not fiat_symbol:
            fiat_symbol = FIAT_DEFAULT_SYMBOL.lower()
        else:
            fiat_symbol = fiat_symbol.lower()

        if crypto_symbol:
            # TODO fix error here...
            ids = get_coingecko_id(crypto_symbol)
            uri = 'https://api.coingecko.com/api/v3/simple/price?ids={}&vs_currencies={}'.format(ids, fiat_symbol)
            req = requests.get(uri)
            rate_data = json.loads(req.content)
            crypto_rate_in_fiat = rate_data.get(ids).get(fiat_symbol)
            result = crypto_rate_in_fiat
    except Exception as e:
        raise Exception('Error getting current fiat rate of {} {}'.format(crypto_symbol, e))

    return result


def get_coingecko_id(symbol):
    metadata = get_coingecko_meta()
    result = None
    for m in metadata:
        if m.get('symbol').lower() == symbol.lower(): \
                result = m.get('id')
    return result


def get_coingecko_meta():
    coingecko_meta_file = ''.join([os.getcwd(), COINGECKO_META])
    if not os.path.isfile(coingecko_meta_file):
        uri = "https://api.coingecko.com/api/v3/coins/list"
        req = requests.get(uri)
        coingecko_meta = json.loads(req.content)
        write_coingecko_meta(coingecko_meta)
        result = coingecko_meta
    else:
        with open(coingecko_meta_file) as data_file:
            result = json.loads(data_file.read())
    return result


def write_coingecko_meta(data):
    markets_location = ''.join([os.getcwd(), COINGECKO_META])
    with open(markets_location, 'w') as outfile:
        json.dump(data, outfile, indent=2)


class CommonError(Exception):
    pass
