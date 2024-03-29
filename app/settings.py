import logging
from app.apikeys import *

FIAT_DEFAULT_SYMBOL = 'GBP'
# This should be set to a value based in the fiat default symol above. e.g. 1 = 1 GBP
FIAT_ARBITRAGE_MINIMUM = 0

DEFAULT_CURRENCY = 'ETH'
DB_HOST = 'localhost'
DB_PORT_JOBQUEUE = 27017
DB_NAME_JOBQUEUE = 'jobqueue'
DB_NAME_TRADES = 'trades'
DB_NAME_AUDIT = 'audit'
DB_NAME_COMMON = 'common'
DB_NAME_EXCHANGE = 'exchange'

# EXCHANGES = ['binance', 'bittrex', 'hitbtc', 'poloniex', 'p2pb2b']
# EXCHANGES = ['binance', 'bittrex', 'hitbtc', 'poloniex']
EXCHANGES = ['binance', 'hitbtc']

TRADE_PAIRS = [
    'ETH-BTC', 'ETC-ETH', 'LTC-BTC', 'REP-ETH', 'GNT-ETH', 'ZRX-ETH',
]
# TRADE_PAIRS = ['ETH-BTC']
# TRADE_PAIRS = ['ARDR-BTC']
LOGLEVEL = 'DEBUG'
# JOBS_NOT_RUNNING = []
JOBS_NOT_RUNNING = ['TRANSACT', 'REPLENISH']

INTERVAL_COMPARE = int(5)
INTERVAL_NEWJOBS = int(1)
INTERVAL_RUNNINGJOBS = int(3)
# get a new fiat rate every 10 mins
INTERVAL_FIAT_RATE = int(600)

MASTER_EXCHANGE = 'bittrex'
FIAT_REPLENISH_AMOUNT = 1000
