from binance.client import Client, BinanceWithdrawException
from app.settings import BINANCE_SECRET_KEY, BINANCE_PUBLIC_KEY
import time
from decimal import Decimal
import math
import logging
from app.lib.exchange import exchange

BITTREX_TAKER_FEE = 0.0025

BITTREX_ERROR_CODES = [
    {'success': False, 'message': 'INVALID_SIGNATURE', 'result': None, 'explanation': None},
    {"success": False, "message": "DUST_TRADE_DISALLOWED_MIN_VALUE_50K_SAT", "result": None},
    {'success': False, 'message': 'NO_API_RESPONSE', 'result': None},
    {'success': False, 'message': 'UUID_INVALID', 'result': None}
]

MINIMUM_DEPOSIT = {}


class binance(exchange):
    def __init__(self, jobqueue_id):

        self.api = Client(BINANCE_PUBLIC_KEY, BINANCE_SECRET_KEY)
        self.lowest_ask = None
        self.highest_bid = None
        self.name = 'binance'
        self.jobqueue_id = jobqueue_id
        exchange.__init__(self, name=self.name, jobqueue_id=self.jobqueue_id)

    def order_book(self):
        order_book_dict = self.api.get_order_book(symbol=self.trade_pair, limit=100)
        if order_book_dict.get('error'):
            raise (WrapBinanceError(order_book_dict.get('error')))
        self.asks = [{'price': Decimal(x[0]), 'volume': Decimal(x[1])} for x in
                     order_book_dict.get('asks', [])]
        self.lowest_ask = self.asks[0]
        self.bids = [{'price': Decimal(x[0]), 'volume': Decimal(x[1])} for x in
                     order_book_dict.get('bids', [])]
        self.highest_bid = self.bids[0]
        logging.debug(
            'Binance lowest ask {} highest bid {}'.format(self.lowest_ask['price'], self.highest_bid['price']))
        return order_book_dict

    def get_currency_pairs(self):
        # get all of their currency pairs in the format for the markets file
        currency_pairs_response = self.api.get_exchange_info()
        # {'symbol': 'CVCBTC', 'status': 'TRADING', 'baseAsset': 'CVC', 'baseAssetPrecision': 8, 'quoteAsset': 'BTC', 'quotePrecision': 8, 'orderTypes': ['LIMIT', 'LIMIT_MAKER', 'MARKET', 'STOP_LOSS_LIMIT', 'TAKE_PROFIT_LIMIT'], 'icebergAllowed': True, 'filters': [{'filterType': 'PRICE_FILTER', 'minPrice': '0.00000001', 'maxPrice': '100000.00000000', 'tickSize': '0.00000001'}
        currency_pairs_list = []
        fees_dict = self.get_currency_fees()
        for c in currency_pairs_response.get('symbols'):
            if c['status'] == 'TRADING':
                currency_pairs_list.append({
                    'name': '-'.join([c['baseAsset'], c['quoteAsset']]),
                    'trading_code': c['symbol'],
                    'base_currency': c['baseAsset'],
                    'quote_currency': c['quoteAsset'],
                    'decimal_places': -int(math.log10(
                        Decimal([x.get('stepSize') for x in c['filters'] if x['filterType'] == 'LOT_SIZE'][0]))) + 1,
                    'min_trade_size':
                        [float(x.get('minQty')) for x in c['filters'] if x['filterType'] == 'LOT_SIZE'][0],
                    'min_trade_size_currency': c['baseAsset'],
                    'min_notional':
                        [float(x.get('minNotional')) for x in c['filters'] if x['filterType'] == 'MIN_NOTIONAL'][0],
                    'taker_fee': float(fees_dict.get(c.get('symbol')).get('taker_fee')),
                    'maker_fee': float(fees_dict.get(c.get('symbol')).get('maker_fee')),
                    # just use taker for now as it will always be more than maker. so we will under estimate profit
                    'fee': float(fees_dict.get(c.get('symbol')).get('taker_fee'))
                })

        return currency_pairs_list

    def get_currency_fees(self):
        try:
            fees_response = self.api.get_trade_fee()
        except BinanceWithdrawException as e:
            raise WrapBinanceError('Error getting currency fees: {}'.format(e))

        return {x.get('symbol'):
                    {'maker_fee': x.get('maker'), 'taker_fee': x.get('taker')}
                for x in fees_response.get('tradeFee')}

    def trade(self, trade_type, volume, price, trade_id=None):
        result = None
        if trade_type == 'buy':
            result = self.api.order_limit_buy(symbol=self.trade_pair, quantity=volume, price=price)
        elif trade_type == 'sell':
            result = self.api.order_limit_sell(symbol=self.trade_pair, quantity=volume, price=price)

        if not result.get('status'):
            raise WrapBinanceError('{}'.format(result.get('message')))

        if result.get('status').upper() == 'FILLED':
            raw_trade = result
        else:
            raw_trade = self.get_order_status(result.get('orderId'))

        if not raw_trade.get('status').upper() == 'FILLED':
            raise WrapBinanceError('{}'.format(result.get('message')))

        trade = self.format_trade(raw_trade, trade_type, trade_id)

        return trade

    def get_order_status(self, order_id):
        order_completed = False
        order_result = {}
        while not order_completed:
            order_result = self.get_order(order_id=order_id)
            if order_result['status'].upper() == 'FILLED':
                break
            time.sleep(5)

        return order_result

    def get_order(self, order_id):
        return self.api.get_order(symbol=self.trade_pair, orderId=order_id)

    def get_orders(self, order_id):
        return

    def format_trade(self, raw_trade, trade_type, trade_id):

        # {'symbol': 'ADXBTC', 'orderId': 26852121, 'clientOrderId': 'CCEUFAceue5R2wksYE3FYo',
        #  'transactTime': 1548755950370, 'price': '0.00002606', 'origQty': '39.00000000', 'executedQty': '39.00000000',
        #  'cummulativeQuoteQty': '0.00101634', 'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'LIMIT', 'side': 'BUY',
        #  'fills': [{'price': '0.00002606', 'qty': '39.00000000', 'commission': '0.03900000', 'commissionAsset': 'ADX',
        #             'tradeId': 3522988}]}

        # {'symbol': 'ETHBTC', 'orderId': 271097202, 'clientOrderId': 'A584YfHssjyLZkVNdehqlB', 'price': '0.03076800',
        #  'origQty': '0.03400000', 'executedQty': '0.03400000', 'cummulativeQuoteQty': '0.00104611', 'status': 'FILLED',
        #  'timeInForce': 'GTC', 'type': 'LIMIT', 'side': 'SELL', 'stopPrice': '0.00000000', 'icebergQty': '0.00000000',
        #  'time': 1548786572329, 'updateTime': 1548786572444, 'isWorking': True}

        try:
            trade = {
                'external_id': raw_trade['orderId'],
                '_id': str(trade_id),
                'status': 'Closed',
                'trade_pair_common': self.trade_pair_common,
                'trade_pair': self.trade_pair,
                'trade_type': trade_type,
                'price': raw_trade['price'],
                'volume': raw_trade['executedQty'],
                'trades_itemised': raw_trade.get('fills', []),
                # seems like either one of these can be present
                'date': raw_trade.get('transactTime') or raw_trade.get('time'),
                'fees': self.calculate_fees(raw_trade['fills'], raw_trade['price']),
                'exchange': self.name
            }
        except Exception as e:
            raise WrapBinanceError('Error formatting trade {}'.format(e))

        return trade

    def get_balances(self):
        try:
            balances = {x.get('asset'): Decimal(x.get('free')) for x in self.api.get_account().get('balances')}
        except Exception as e:
            raise Exception('Error getting trading balances {}'.format(e))
        self.balances = balances

    def get_address(self, symbol):
        try:
            address_json = self.api.get_deposit_address(asset=symbol)
        except Exception as e:
            raise Exception('Error getting currency address in Binance {}'.format(e))
        return address_json.get('address')

    def calculate_fees(self, trades_itemised, price):
        total_commission = 0
        for trade in trades_itemised:
            total_commission += Decimal(trade.get('commission'))
        total_commission_in_btc = total_commission * Decimal(price)
        result = str(total_commission_in_btc.normalize())
        return result

    def get_pending_balances(self):
        try:
            deposit_history = self.api.get_deposit_history()
            pending_balances = {x.get('asset'): Decimal(x.get('amount')) for x in deposit_history['depositList'] if
                                x.get('status') == 0}
        except Exception as e:
            raise Exception('Error getting pending balances {}'.format(e))
        self.pending_balances = pending_balances


class WrapBinanceError(Exception):
    pass
