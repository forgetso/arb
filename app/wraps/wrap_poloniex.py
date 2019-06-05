from poloniex import Poloniex
from app.settings import POLONIEX_SECRET_KEY, POLONIEX_PUBLIC_KEY
from app.lib.errors import ErrorTradePairDoesNotExist
import time
from decimal import Decimal, Context, setcontext
import math
from app.lib.common import round_decimal_number, get_number_of_decimal_places
from app.lib.exchange import exchange

POLONIEX_TAKER_FEE = 0.002
POLONIEX_MAKER_FEE = 0.0008

POLONIEX_ERROR_CODES = []

MINIMUM_DEPOSIT = {}


class poloniex(exchange):
    def __init__(self, jobqueue_id):

        self.api = Poloniex(POLONIEX_PUBLIC_KEY, POLONIEX_SECRET_KEY)
        self.name = 'poloniex'
        exchange.__init__(self, name=self.name, jobqueue_id=jobqueue_id)

    def order_book(self):
        ticker = self.api.returnOrderBook()
        order_book_dict = ticker[self.trade_pair]
        if order_book_dict.get('error'):
            raise (WrapPoloniexError(order_book_dict.get('error')))
        # ticker contains lowest ask and highest bid. we will only use this info as we currently don't care about other bids
        self.asks = [order_book_dict.get('asks')]
        self.lowest_ask = {'price': Decimal(self.asks[0][0][0]), 'volume': Decimal(self.asks[0][0][1])}
        self.bids = [order_book_dict.get('bids')]
        self.highest_bid = {'price': Decimal(self.bids[0][0][0]), 'volume': Decimal(self.bids[0][0][1])}
        return order_book_dict

    def get_currency_pairs(self):
        # get all of their currency pairs in the format for the markets file
        currency_pairs_response = self.api.returnTicker()
        # {"BTC_BCN":{"id":7,"last":"0.00000019","lowestAsk":"0.00000019","highestBid":"0.00000018","percentChange":"0.05555555","baseVolume":"31.34657914","quoteVolume":"167711796.95537490","isFrozen":"0","high24hr":"0.00000019","low24hr":"0.00000018"}
        currency_pairs_list = []
        for symbol, c in currency_pairs_response.items():
            symbol_split = symbol.split('_')
            if c['isFrozen'] == 0:
                currency_pairs_list.append({
                    # poloniex names things the opposite way round to other exchanges BTC_ETH instead of ETH_BTC
                    'name': '{}-{}'.format(symbol_split[1], symbol_split[0]),
                    'trading_code': symbol,
                    'base_currency': symbol_split[0],
                    'quote_currency': symbol_split[1],
                    'decimal_places': get_number_of_decimal_places(str(c['highestBid'])),
                    # this seems to be the minimum trade size for all currencies on their site
                    'min_trade_size': float(0.0001),
                    'min_trade_size_currency': symbol_split[1],
                    'maker_fee': POLONIEX_MAKER_FEE,
                    'taker_fee': POLONIEX_TAKER_FEE,
                    # just use taker for now as it will always be more than maker. so we will under estimate profit
                    'fee': POLONIEX_TAKER_FEE,
                })

        return currency_pairs_list

    def trade(self, trade_type, volume, price, trade_id=None):
        result = None
        if trade_type == 'buy':
            result = self.api.buy(currencyPair=self.trade_pair, amount=volume, rate=price)
        elif trade_type == 'sell':
            result = self.api.sell(currencyPair=self.trade_pair, amount=volume, rate=price)

        if not result.get('status'):
            raise WrapPoloniexError('{}'.format(result.get('message')))

        if result.get('status').upper() == 'FILLED':
            raw_trade = result
        else:
            raw_trade = self.get_order_status(result.get('orderId'))

        if not raw_trade.get('status').upper() == 'FILLED':
            raise WrapPoloniexError('{}'.format(result.get('message')))

        trade = self.format_trade(raw_trade, trade_type, trade_id)

        return trade

    def get_order_status(self, order_id):
        # TODO work out how these responses works
        order_completed = False
        order_result = {}
        while not order_completed:
            order_result = self.get_orders()
            if order_id not in order_result:
                break
            time.sleep(5)

        return order_result

    # TODO why would you need to put an order ID for get orders?
    def get_orders(self, order_id):
        return self.api.returnOpenOrders(currencyPair=self.trade_pair)

    def get_order(self, order_id):
        raise NotImplementedError('Get Order not implemented in Poloniex Wrapper')

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
            raise WrapPoloniexError('Error formatting trade {}'.format(e))

        return trade

    def get_balances(self):
        try:
            response = self.api.returnAvailableAccountBalances()
            if not response:
                balances = {}
            else:
                balances = {symbol: balance for symbol, balance in response.get('exchange')}
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


class WrapPoloniexError(Exception):
    pass
