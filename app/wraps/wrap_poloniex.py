from poloniex import Poloniex
from app.settings import POLONIEX_SECRET_KEY, POLONIEX_PUBLIC_KEY
import time
from decimal import Decimal
from app.lib.common import get_number_of_decimal_places
from app.lib.exchange import exchange
from datetime import datetime, timedelta
from app.lib.jobqueue import return_value_to_stdout

POLONIEX_TAKER_FEE = 0.002
POLONIEX_MAKER_FEE = 0.0008

POLONIEX_ERROR_CODES = []

MINIMUM_DEPOSIT = {}


class poloniex(exchange):
    def __init__(self, jobqueue_id):

        self.api = Poloniex(POLONIEX_PUBLIC_KEY, POLONIEX_SECRET_KEY)
        self.name = 'poloniex'
        exchange.__init__(self, name=self.name, jobqueue_id=jobqueue_id)

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        # Remove the unpicklable entries.
        del state['api']
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)
        # API cannot be pickled
        self.api = Poloniex(POLONIEX_PUBLIC_KEY, POLONIEX_SECRET_KEY)

    def order_book(self):
        ticker = self.api.returnOrderBook()
        order_book_dict = ticker[self.trade_pair]
        if order_book_dict.get('error'):
            raise (WrapPoloniexError(order_book_dict.get('error')))
        # ticker contains lowest ask and highest bid. we will only use this info as we currently don't care about other bids
        # data is an array of prices and volumes
        # [['0.00952008', 0.0008061], ['0.00954239', 52.47959867], ['0.00954240', 5], ['0.00954490', 25], ... ]
        self.asks = [{'price': Decimal(x[0]), 'volume': Decimal(x[1])} for x in order_book_dict.get('asks')]
        self.lowest_ask = self.asks[0]
        self.bids = [{'price': Decimal(x[0]), 'volume': Decimal(x[1])} for x in order_book_dict.get('bids')]
        self.highest_bid = self.bids[1]
        # return_value_to_stdout(self.__getstate__())

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
                    'base_currency': symbol_split[1],
                    'quote_currency': symbol_split[0],
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

        # Returns something like this
        # {'orderNumber': 613107503923, 'resultingTrades': [
        #     {'amount': 0.011, 'date': '2019-07-03 15:48:19', 'rate': 0.02579294, 'total': 0.00028372,
        #      'tradeID': 47232767, 'type': 'buy', 'takerAdjustment': 0.0109725}], 'fee': 0.0025,
        #  'currencyPair': 'BTC_ETH'}
        if not result.get('orderNumber'):
            raise WrapPoloniexError('{}'.format(result))

        # [{globalTradeID: 394127362,
        #   tradeID: 13536351,
        #   currencyPair: 'BTC_STR',
        #   type: 'buy',
        #   rate: '0.00003432',
        #   amount: '3696.05342780',
        #   total: '0.12684855',
        #   fee: '0.00200000',
        #   date: '2018-10-16 17:03:43'},
        #  ...]
        raw_trades = self.get_order_status(result.get('orderNumber'))

        result['resultingTrades'] = raw_trades

        trade = self.format_trade(result, trade_type, trade_id)

        return trade

    def get_order_status(self, order_id):
        # TODO work out how these responses works
        order_completed = False
        order_result = []
        while not order_completed:
            response = self.api.returnOrderTrades(order_id)
            if 'error' not in response:
                order_completed = True
                order_result = response

            time.sleep(5)

        return order_result

    # TODO why would you need to put an order ID for get orders?
    def get_orders(self, order_id):
        return self.api.returnOpenOrders(currencyPair=self.trade_pair)

    def get_order(self, order_id):
        raise NotImplementedError('Get Order not implemented in Poloniex Wrapper')

    def format_trade(self, raw_trade, trade_type, trade_id):

        # {'orderNumber': 613107503923, 'resultingTrades': [
        #     {'amount': 0.011, 'date': '2019-07-03 15:48:19', 'rate': 0.02579294, 'total': 0.00028372,
        #      'tradeID': 47232767, 'type': 'buy', 'takerAdjustment': 0.0109725}], 'fee': 0.0025,
        #  'currencyPair': 'BTC_ETH'}
        try:
            trade = {
                'external_id': raw_trade['orderNumber'],
                '_id': str(trade_id),
                'status': 'Closed',
                'trade_pair_common': self.trade_pair_common,
                'trade_pair': self.trade_pair,
                'trade_type': trade_type,
                'price': raw_trade['resultingTrades'][0]['rate'],
                'trades_itemised': raw_trade.get('resultingTrades', []),
                'date': raw_trade['resultingTrades'][0]['date'],
                'fees': raw_trade['takerAdjustment'],
                'exchange': self.name
            }
            volume = 0
            for individual_trade in trade['trades_itemised']:
                volume += Decimal(individual_trade['amount'])

            trade['volume'] = volume
        except Exception as e:
            raise WrapPoloniexError('Error formatting trade {}'.format(e))

        return trade

    def get_balances(self):
        try:
            response = self.api.returnAvailableAccountBalances()
            if not response:
                balances = {}
            else:
                balances = {symbol: balance for symbol, balance in response.get('exchange').items()}
        except Exception as e:
            raise Exception('Error getting trading balances {}'.format(e))
        self.balances = balances

    def get_address(self, symbol):
        try:
            addresses_json = self.api.returnDepositAddresses()
        except Exception as e:
            raise Exception('Error getting currency address in Poloniex {}'.format(e))
        address = addresses_json.get(symbol)
        if isinstance(address, int):
            # poloniex gives deposit address as int
            address = hex(address)
        return address

    def calculate_fees(self, trades_itemised, price):
        total_commission = 0
        for trade in trades_itemised:
            total_commission += Decimal(trade.get('commission'))
        total_commission_in_btc = total_commission * Decimal(price)
        result = str(total_commission_in_btc.normalize())
        return result

    def get_pending_balances(self):
        try:
            end = datetime.utcnow()
            start = end - timedelta(minutes=5)
            deposit_history = self.api.returnDeposits(start.timestamp(), end.timestamp())
            pending_balances = {x.get('currency'): Decimal(x.get('amount')) for x in deposit_history if
                                x.get('status') == 'PENDING'}
        except Exception as e:
            raise Exception('Error getting pending balances {}'.format(e))
        self.pending_balances = pending_balances


class WrapPoloniexError(Exception):
    pass
