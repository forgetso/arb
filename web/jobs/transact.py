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
from web.lib.db import store_trade
from web.lib.common import dynamically_import_exchange


def transact(exchange, trade_pair_common, volume, price, type, markets, test_transaction=False):
    logging.info(
        'Instructed to *{}* trade pair {} volume {} at price {} on {}'.format(type, trade_pair_common, volume, price,
                                                                              exchange))
    logging.info('Trade pair {} has base currency of {}'.format(trade_pair_common,
                                                                markets[exchange][trade_pair_common]['base_currency']))
    trade = {}
    trade_id = get_trade_id()

    exchange_obj = dynamically_import_exchange(exchange)()
    exchange_obj.set_trade_pair(trade_pair_common, markets)

    # just check that we can actually transact by placing the minimum transaction
    # TODO actually connect up sandbox APIs if they exist
    if test_transaction:
        logging.debug('Setting price for test transaction')
        exchange_obj.order_book()
        price = exchange_obj.lowest_ask['price']

    trade_valid, price, volume = exchange_obj.trade_validity(price=price, volume=volume)

    if trade_valid:
        # we convert Decimal objects to str for the API requests
        try:
            volume_str = str(volume)
            price_str = str(price)
        except Exception as e:
            raise TransactionError('Error converting price/volume to str {}'.format(e))

        logging.debug('Trading volume {} price {} notional {}'.format(volume_str, price_str, price * volume))
        trade = exchange_obj.trade(trade_type=type, volume=volume_str, price=price_str, trade_id=trade_id)
        logging.debug(trade)
        if trade:
            trade['type'] = 'TRANSACT'
            trade['_id'] = trade_id
            logging.debug(trade)
            store_trade(trade)
            return_value_to_stdout(trade)

    return trade


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
    price = Decimal(args.price).normalize()
    volume = Decimal(args.volume).normalize()

    transact(args.exchange, args.trade_pair_common, volume, price, args.type, markets, args.test_transaction)


class TransactionError(Exception):
    pass


setup()
