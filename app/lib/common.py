from app.settings import FIAT_REPLENISH_AMOUNT, FIAT_DEFAULT_SYMBOL, EXCHANGES
from math import log10, log2, modf, floor
from decimal import Decimal, Context, setcontext
import os, json, requests
import logging
from app.settings import LOGLEVEL
import importlib

logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)



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
