import sys

if sys.version_info < (3, 0):
    print("Python 2.x, not Python 3.x")
    print(sys.path)
    # sys.exit(1)

import argparse
from web.settings import LOGLEVEL
from web.lib.db import jobqueue_db, trades_db
from web.lib.jobqueue import JOB_COLLECTION
import logging
from web.lib.setup import load_currency_pairs
import importlib
import os
import uuid
from web.lib.jobqueue import return_value_to_stdout
from decimal import Decimal, Context, setcontext


def transact(exchange, trade_pair_common, volume, price, type, markets, test_transaction=False):
    logging.info(
        'Instructed to *{}* trade pair {} volume {} at price {} on {}'.format(type, trade_pair_common, volume, price,
                                                                              exchange))
    logging.info('Trade pair {} has base currency of {}'.format(trade_pair_common,
                                                                markets[exchange][trade_pair_common]['base_currency']))

    trade_id = get_trade_id()

    exchange_obj = get_exchange(exchange)()
    exchange_obj.set_trade_pair(trade_pair_common, markets)

    # just check that we can actually transact by placing the minimum transaction
    # TODO actually connect up sandbox APIs if they exist
    if test_transaction:
        logging.debug('Setting price for test transaction')
        exchange_obj.order_book()
        price = exchange_obj.lowest_ask['price']

    # if an exchange has a minimum trade size and our price is less than this, we must use the minimum trade size
    # minimum trade size is measured in non-BTC, e.g. ETH, ADX, NEO, etc.
    if hasattr(exchange_obj, 'min_trade_size') and price < exchange_obj.min_trade_size:
        volume = exchange_obj.min_trade_size

    # if an exchange has a minimum trade size in BTC, we need to make sure our BTC trade amount is greater than or equal to this
    if hasattr(exchange_obj, 'min_trade_size_btc'):
        if hasattr(exchange_obj, 'decimal_places'):
            # binance has a min BTC trade size and also decimal places per trading pair
            allowed_decimal_places = int(exchange_obj.decimal_places)
        else:
            # otherwise we work out the decimal places from the min trade size
            allowed_decimal_places = get_number_of_decimal_places(exchange_obj.min_trade_size)
        decimal_rounding_context = Context(prec=allowed_decimal_places)
        setcontext(decimal_rounding_context)

        # finally, check if the volume we're attempting to trade is above the min trade size in BTC
        if price * volume < exchange_obj.min_trade_size_btc:
            volume = exchange_obj.min_trade_size_btc / price + exchange_obj.min_trade_size,

    # otherwise if an exchange only specifies a set number of decimal places (gatecoin), we can use this in isolation
    elif hasattr(exchange_obj, 'decimal_places'):
        decimal_rounding_context = Context(prec=int(exchange_obj.decimal_places))
        setcontext(decimal_rounding_context)
        volume = volume * Decimal(1)
        # TODO following code was for test transactions, need to reinstate
        # volume = 10 ** -exchange_obj.decimal_places / price

    trade = exchange_obj.trade(trade_type=type, volume=str(volume), price=price, trade_id=trade_id)

    if trade:
        store_trade(trade)
        return_value_to_stdout(trade)

    return trade


def get_number_of_decimal_places(number):
    try:
        print(number)

        decimal_part = str(number).split('.')[1]

        if decimal_part == '0':
            decimal_places = 0
        else:
            decimal_places = len(decimal_part)
    except Exception as e:
        raise TransactionError('Error getting decimal places {}'.format(e))
    return decimal_places


def store_trade(trade):
    db = trades_db()
    db.trades.update_one({'_id': trade.get('_id')}, {'$set': trade}, upsert=True)


def get_exchange(exchange):
    try:
        module_name = 'web.wraps.wrap_{}'.format(exchange)
        exchange_module = importlib.import_module(module_name)
        if hasattr(exchange_module, exchange):
            exchange_class = getattr(exchange_module, exchange)
            return exchange_class
        else:
            raise Exception('exchange module does not have class {}'.format(exchange))
    except ImportError:
        raise Exception('Could not import {}'.format(exchange))


def get_trade_id():
    job_pid = os.getpid()
    db = jobqueue_db()
    this_job = db[JOB_COLLECTION].find_one({'job_pid': job_pid})
    if this_job:
        trade_id = this_job.get('_id')
    else:
        # we may be running the job outside of the job queue
        trade_id = uuid.uuid4().hex.replace('-', '')[0:23]
    return str(trade_id)


def setup():
    parser = argparse.ArgumentParser(description='Buy or sell a trade pair')

    parser.add_argument('exchange', type=str, help='Exchange on which to perform transaction')
    parser.add_argument('trade_pair_common', type=str, help='Trade pair to transact in ')
    parser.add_argument('volume', type=str, help='Volume to buy')
    parser.add_argument('price', type=str, help='Price to buy at')
    parser.add_argument('type', type=str, help='Buy or sell')
    parser.add_argument('--test_transaction', default=False, action='store_true',
                        help='Try a transaction for the minimum amount')
    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)
    markets = load_currency_pairs()
    price = Decimal(args.price)
    volume = Decimal(args.volume)

    transact(args.exchange, args.trade_pair_common, volume, price, args.type, markets, args.test_transaction)


class TransactionError(Exception):
    pass


setup()
