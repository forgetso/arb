from app.settings import FIAT_REPLENISH_AMOUNT, FIAT_DEFAULT_SYMBOL
from math import log10, log2, modf, floor
from decimal import Decimal, Context, setcontext
import os, json, requests
import logging
from app.settings import LOGLEVEL
import importlib

logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)
COINGECKO_META = "/app/coingecko_meta.json"


def get_replenish_quantity(fiat_rate):
    try:
        quantity = FIAT_REPLENISH_AMOUNT / fiat_rate
    except Exception as e:
        raise CommonError('Error getting replenish quantity {}'.format(e))

    return quantity


def get_number_of_decimal_places(number):
    if not isinstance(number, Decimal) or not isinstance(number, str) or not isinstance(number, float):
        raise TypeError('number must be of type Decimal or str or float')
    try:
        # turns out decimal has the length of the decimal part built in
        decimal_places = Decimal(number).as_tuple()[2] * -1
    except Exception as e:
        raise CommonError('Error getting decimal places {}'.format(e))
    return decimal_places


def get_number_of_places_before_point(number):
    try:
        # http://mathworld.wolfram.com/NumberLength.html
        log_10_number = log10(number)
        if log_10_number < 0:
            places = 1
        else:
            places = floor(log_10_number) + 1
    except Exception as e:
        raise CommonError('Error getting places before decimal point {}'.format(e))
    return places


# rounds a float or a Decimal to a certain number of decimal places and returns it as a Decimal
def round_decimal_number(number, decimal_places):
    try:
        # logging.debug('Number is  {}'.format(number))
        places_before_point = get_number_of_places_before_point(number)
        # prec=1 implies no decimal places, e.g. 5.45 rounds to 5
        precision = decimal_places + places_before_point
        if precision == 0:
            precision = 1
        # logging.debug('Precision set to {}'.format(precision))
        # logging.debug('Decimal places {}'.format(decimal_places))

        decimal_part = modf(number)[0]
        if decimal_part == 0.0 and decimal_places == 0:
            return Decimal(number)

        context = Context(prec=int(precision))
        setcontext(context)
        # rounds the volume to the correct number of decimal places
        # logging.debug('Rounding to {} decimal_places'.format(decimal_places))

        if decimal_places > 0:
            quantize_accuracy = Decimal('1.{}'.format(decimal_places * '0'))
        else:
            quantize_accuracy = Decimal(1)
        # logging.debug('Accuracy set to {} '.format(quantize_accuracy))

        number_corrected = Decimal(number).normalize().quantize(quantize_accuracy)
    except Exception as e:
        raise CommonError('Error rounding decimal number: {}'.format(e))

    return number_corrected


def get_current_fiat_rate(crypto_symbol, fiat_symbol=None):
    crypto_symbol = crypto_symbol.lower()
    result = None
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


def dynamically_import_exchange(exchange):
    try:
        module_name = 'app.wraps.wrap_{}'.format(exchange)
        exchange_module = importlib.import_module(module_name)
        if hasattr(exchange_module, exchange):
            exchange_class = getattr(exchange_module, exchange)
            return exchange_class
        else:
            raise Exception('exchange module does not have class {}'.format(exchange))
    except ImportError:
        raise Exception('Could not import {}'.format(exchange))


class CommonError(Exception):
    pass
