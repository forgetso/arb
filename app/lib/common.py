from app.settings import FIAT_REPLENISH_AMOUNT, FIAT_DEFAULT_SYMBOL, EXCHANGES
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
    if not isinstance(number, Decimal) and not isinstance(number, str) and not isinstance(number, float):
        raise TypeError('number must be of type Decimal or str or float not {} {}'.format(type(number), number))
    try:
        if isinstance(number, float):
            decimal_places = Decimal(str(number)).as_tuple()[2] * -1
        else:
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


def build_fiat_rates_uri(crypto_symbols, fiat_symbol):
    ids = []
    meta_data = get_coingecko_meta()
    for crypto_symbol in crypto_symbols:
        idsx = get_coingecko_id(crypto_symbol.lower(), meta_data)
        ids.append(idsx.lower())
    fiat_symbol = get_fiat_symbol(fiat_symbol).lower()
    uri = 'https://api.coingecko.com/api/v3/simple/price?ids={}&vs_currencies={}'.format(','.join(ids), fiat_symbol)
    return uri


def get_current_fiat_rates(crypto_symbols, fiat_symbol=None):
    if isinstance(crypto_symbols, str):
        crypto_symbols_set = {crypto_symbols}
    else:
        crypto_symbols_set = crypto_symbols
    if not isinstance(crypto_symbols_set, set):
        raise TypeError(
            'Pass a set of crypto symbols for which to find fiat rates. You passed {}'.format(type(crypto_symbols_set)))
    uri = build_fiat_rates_uri(crypto_symbols, fiat_symbol)
    req = requests.get(uri)
    coingecko_rates_data = req.json()
    rates_data = {}
    meta_data = get_coingecko_meta()
    fiat_symbol_key = get_fiat_symbol(fiat_symbol).upper()
    for crypto_symbol in crypto_symbols_set:
        coingecko_symbol = get_coingecko_id(crypto_symbol.lower(), meta_data)
        rates_data[crypto_symbol] = {
            fiat_symbol_key: coingecko_rates_data.get(coingecko_symbol).get(fiat_symbol_key.lower())
        }
    return rates_data


def get_fiat_symbol(fiat_symbol):
    if not fiat_symbol:
        fiat_symbol = FIAT_DEFAULT_SYMBOL
    else:
        fiat_symbol = fiat_symbol
    return fiat_symbol


def get_current_fiat_rate(crypto_symbol, fiat_symbol=None):
    rate_json = get_current_fiat_rates(crypto_symbol, fiat_symbol)
    fiat_symbol = get_fiat_symbol(fiat_symbol).lower()
    rate = rate_json.get(crypto_symbol).get(fiat_symbol)
    return rate


def get_coingecko_id(symbol, metadata):
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


def dynamically_import_exchange(exchange, directory=None):
    try:
        if not directory:
            directory = 'app.wraps.wrap'
        module_name = '{}_{}'.format(directory, exchange)
        exchange_module = importlib.import_module(module_name)
        if hasattr(exchange_module, exchange):
            exchange_class = getattr(exchange_module, exchange)
            return exchange_class
        else:
            raise Exception('exchange module does not have class {}'.format(exchange))
    except ImportError as e:
        raise ImportError('Could not import {}: {}'.format(exchange, e))


def check_pid(pid):
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def decimal_as_string(number):
    # float returns stupid strings like 4.5e-05
    # float also contains rounding errors
    # so we make things into Decimals
    # Decimals automatically round to 20 places or something, even if this includes loads of trailing zeroes
    # so we use normalize to strip the trailing zeroes
    try:
        if isinstance(number, Decimal):
            result = str(number)
        else:
            result = str(Decimal(number).normalize())
    except:
        raise CommonError(
            'Decimal as string expects a numeric values to be converted to a decimal. You passed {} {}'.format(
                number,
                type(number)))
    return result


def get_exchanges():
    return EXCHANGES


class CommonError(Exception):
    pass
