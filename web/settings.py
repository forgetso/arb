import logging
from web.apikeys import *

FIAT_DEFAULT_SYMBOL = 'GBP'
# This should be set to a value based in the fiat default symol above. e.g. 1 = 1 GBP
FIAT_ARBITRAGE_MINIMUM = 0.0

BASE_CURRENCY = 'BTC'
DB_HOST_JOBQUEUE = 'localhost'
DB_PORT_JOBQUEUE = 27017
DB_NAME_JOBQUEUE = 'jobqueue'
DB_NAME_TRADES = 'trades'

TRADE_PAIRS = [
    '1ST-BTC',
    'ADX-BTC',
    'ADX-ETH',
    'AMB-BTC',
    'AMB-ETH',
    'AVT-ETH',
    #'BCH-BTC',
    #'BTC-USD',
    'CDT-BTC',
    'CDT-ETH',
    'CLN-BTC',
    'CLN-ETH',
    'ETH-BTC',
    # 'ETH-DAI',
    # 'ETH-USD',
    # 'GUP-BTC',
    # 'HGT-BTC',
    # 'HGT-ETH',
    # 'HVN-BTC',
    # 'HVN-ETH',
    # 'IFT-BTC',
    # 'IND-ETH',
    # 'LOC-BTC',
    # 'LOC-ETH',
    # 'LTC-BTC',
    # 'LTC-ETH',
    # 'LTC-USD',
    # 'MAN-BTC',
    # 'MAN-ETH',
    # 'MKR-BTC',
    # 'MKR-ETH',
    # 'PIX-BTC',
    # 'PIX-ETH',
    # 'REP-BTC',
    # 'RLC-BTC',
    # 'SNT-BTC',
    # 'SNT-ETH',
    # 'XTZ-BTC',
    # 'XTZ-USD',
    # 'ZRX-BTC',
    # 'ZRX-ETH'
]
LOGLEVEL = 'DEBUG'
#JOBS_NOT_RUNNING = ['TRANSACT']
JOBS_NOT_RUNNING = []

INTERVAL_COMPARE = int(10)
INTERVAL_NEWJOBS = int(1)
INTERVAL_RUNNINGJOBS = int(3)
# get a new fiat rate every 10 mins
INTERVAL_FIAT_RATE = int(600)

MASTER_EXCHANGE = 'bittrex'
FIAT_REPLENISH_AMOUNT = 10
