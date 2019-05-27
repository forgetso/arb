from p2pb2bapi import P2PB2B
from app.settings import P2PB2B_SECRET_KEY, P2PB2B_PUBLIC_KEY
from app.lib.errors import ErrorTradePairDoesNotExist
from decimal import Decimal, Context, setcontext
from app.lib.common import round_decimal_number
from app.lib.db import store_balances, get_balances, store_api_access_time, get_api_access_time, lock_api_method, \
    unlock_api_method, get_api_method_lock, get_minutely_api_requests, get_secondly_api_requests
import logging
from datetime import datetime, timedelta
import time

P2PB2B_TAKER_FEE = 0.0020
P2PB2B_MAKER_FEE = 0.0020
P2PB2B_API_RATE_LIMIT_MINUTELY = 100
P2PB2B_API_RATE_LIMIT_SECONDLY = 5
P2PB2B_ERROR_CODES = []

MINIMUM_DEPOSIT = {'BTC': 0.002, 'ETH': 0.05}

# TODO work out a way of automatically importing addresses
P2PB2B_ADDRESSES = {
    'BTC': '36KYvtDUaqFkqmogT1EuHQdhbwML8Ahs9H',
    'ETH': '0x6cA28a73b125b3F1C3760673AacE15A1EF9c3C90',
}


class p2pb2b():
    def __init__(self, jobqueue_id):

        self.api = P2PB2B(P2PB2B_PUBLIC_KEY, P2PB2B_SECRET_KEY)
        self.lowest_ask = None
        self.highest_bid = None
        self.name = 'p2pb2b'
        self.balances = None
        self.balances_time = None
        self.jobqueue_id = jobqueue_id

    def set_trade_pair(self, trade_pair, markets):
        try:
            self.decimal_places = markets.get(self.name).get(trade_pair).get('decimal_places')
            if self.decimal_places:
                self.decimal_places = int(self.decimal_places)
                decimal_rounding_context = Context(prec=self.decimal_places)
                setcontext(decimal_rounding_context)
            self.trade_pair_common = trade_pair
            self.trade_pair = markets.get(self.name).get(trade_pair).get('trading_code')
            self.fee = Decimal(markets.get(self.name).get(trade_pair).get('fee'))
            self.min_trade_size = Decimal(str(markets.get(self.name).get(trade_pair).get('min_trade_size')))
            self.base_currency = markets.get(self.name).get(trade_pair).get('base_currency')
            self.quote_currency = markets.get(self.name).get(trade_pair).get('quote_currency')
        except AttributeError:
            raise ErrorTradePairDoesNotExist

    def order_book(self):
        # TODO put rate limiting in for this wrapper at the very beginning. Store the number of API hits that have occurred in the current minute and second
        # limit is 5 per second or 100 per minute
        order_book_dict = {}
        ticker_buy_response = None
        if get_minutely_api_requests(self.name) < P2PB2B_API_RATE_LIMIT_MINUTELY and get_secondly_api_requests(
                self.name) < P2PB2B_API_RATE_LIMIT_SECONDLY:
            ticker_buy_response = self.api.getBook(market=self.trade_pair, side='buy', limit=1)
            store_api_access_time(self.name, 'order_book', datetime.utcnow())
            if not ticker_buy_response.get('success'):
                raise WrapP2PB2BError(
                    'Error getting order book for {} : {}, {}'.format(self.trade_pair,
                                                                      ticker_buy_response.get('message'),
                                                                      ticker_buy_response))
            order_book_dict['buy'] = ticker_buy_response.get('result')
            ticker_sell_response = self.api.getBook(market=self.trade_pair, side='sell', limit=1)
            store_api_access_time(self.name, 'order_book', datetime.utcnow())
            if not ticker_sell_response.get('success'):
                raise WrapP2PB2BError(
                    'Error getting order book for {} : {}'.format(self.trade_pair, ticker_sell_response.get('message')))
            order_book_dict['sell'] = ticker_sell_response.get('result')
            # print(order_books)
            # {'buy': {'offset': 0, 'limit': 1, 'total': 362, 'orders': [
            #     {'id': 14835298, 'left': '1.375', 'market': 'ETH_BTC', 'amount': '2.909', 'type': 'limit',
            #      'price': '0.029842', 'timestamp': 1556176474.980993, 'side': 'buy', 'dealFee': '0', 'takerFee': '0',
            #      'makerFee': '0', 'dealStock': '1.534', 'dealMoney': '0.045777628'}]},
            #  'sell': {'offset': 0, 'limit': 1, 'total': 408, 'orders': [
            #      {'id': 14855016, 'left': '60.222', 'market': 'ETH_BTC', 'amount': '60.222', 'type': 'limit',
            #       'price': '0.02985', 'timestamp': 1556192089.28709, 'side': 'sell', 'dealFee': '0', 'takerFee': '0.002',
            #       'makerFee': '0.002', 'dealStock': '0', 'dealMoney': '0'}]}}

            # ticker contains lowest ask and highest bid. we will only use this info as we currently don't care about other bids
            self.asks = [{'price': Decimal(x['price']), 'volume': Decimal(x['amount'])} for x in
                         order_book_dict['buy']['orders']]
            self.lowest_ask = self.asks[0]
            self.bids = [{'price': Decimal(x['price']), 'volume': Decimal(x['amount'])} for x in
                         order_book_dict['sell']['orders']]
            self.highest_bid = self.bids[0]
            logging.debug(
                'p2pb2b {} lowest {} highest {}'.format(self.trade_pair_common, self.lowest_ask, self.highest_bid))
        return order_book_dict

    def get_currency_pairs(self):
        # get all of their currency pairs in the format for the markets file
        currency_pairs_response = self.api.getMarkets()
        # {'name': 'ETH_BTC', 'moneyPrec': '6', 'stock': 'ETH', 'money': 'BTC', 'stockPrec': '3', 'feePrec': '4', 'minAmount': '0.001'})
        currency_pairs_list = []
        if not currency_pairs_response.get('success'):
            raise WrapP2PB2BError('Error getting currency pairs')
        for c in currency_pairs_response['result']:
            symbol = c.get('name')
            symbol_split = symbol.split('_')
            # P2PB2B has a limit on the API which means we should only use a few currencies
            if symbol_split[0] in P2PB2B_ADDRESSES and symbol_split[1] in P2PB2B_ADDRESSES:
                currency_pairs_list.append({
                    'name': symbol.replace('_', '-'),
                    'trading_code': symbol,
                    'base_currency': symbol_split[0],
                    'quote_currency': symbol_split[1],
                    'decimal_places': c.get('stockPrec'),
                    'decimal_places_base': c.get('moneyPrec'),
                    'min_trade_size': c.get('minAmount'),
                    'maker_fee': P2PB2B_MAKER_FEE,
                    'taker_fee': P2PB2B_TAKER_FEE,
                    # just use taker for now as it will always be more than maker. so we will under estimate profit
                    'fee': P2PB2B_TAKER_FEE,
                })

        return currency_pairs_list

    def trade(self, trade_type, volume, price, trade_id=None):
        result = None
        response = self.api.newOrder(market=self.trade_pair, side=trade_type, amount=volume, price=price)
        # {
        #     "success": true,
        #     "message": "",
        #     "result": {
        #         "orderId": 25749,
        #         "market": "ETH_BTC",
        #         "price": "0.1",
        #         "side": "sell",
        #         "type": "limit",
        #         "timestamp": 1537535284.828868,
        #         "dealMoney": "0",
        #         "dealStock": "0",
        #         "amount": "0.1",
        #         "takerFee": "0.002",
        #         "makerFee": "0.002",
        #         "left": "0.1",
        #         "dealFee": "0"
        #     }
        # }
        if not response.get('success'):
            raise WrapP2PB2BError('{}'.format(result.get('message')))

        result = response.get('result')
        if result.get('left') == 0:
            raw_trade = result
        else:
            raw_trade = self.get_order_status(result.get('orderId'))

        if not raw_trade.get('left') == 0:
            raise WrapP2PB2BError('{}'.format(result.get('message')))

        trade = self.format_trade(raw_trade, trade_type, trade_id)

        return trade

    def get_order_status(self, order_id):
        order_completed = False
        order_result = {}
        while not order_completed:
            order_response = self.get_order(order_id=order_id)
            if order_response['result']['left'] == 0:
                order_result = order_response['result']
                break
            time.sleep(5)
        return order_result

    def get_order(self, order_id):
        return self.api.getOrder(orderId=order_id)

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
            raise WrapP2PB2BError('Error formatting trade {}'.format(e))

        return trade

    def get_balances(self):
        last_accessed_time = get_api_access_time(self.name, 'get_balances')
        # this api has limits so we've stored the balances in the database in case of querying too frequently
        # fingers crossed they are correct !
        logging.debug('Last accessed time {}'.format(last_accessed_time))
        if self.balances_time and datetime.utcnow() - self.balances_time < timedelta(
                seconds=60) or time.time() - last_accessed_time.timestamp() < 60:
            balances = get_balances(self.name)
            self.balances = balances
            logging.debug('p2pb2b balances already retrieved')
            return

        wait_count = 0
        while get_api_method_lock(self.name, 'get_balances', self.jobqueue_id):
            time.sleep(5)
            wait_count += 1
            if wait_count > 4:
                logging.warning('API method "get_balances" has been locked for more than 20s')
                return

        try:

            lock_api_method(self.name, 'get_balances', self.jobqueue_id)
            balances_response = self.api.getBalances()
            if not balances_response.get('success'):
                raise Exception(balances_response.get('message'))
            unlock_api_method(self.name, 'get_balances', self.jobqueue_id)
            self.balances_time = datetime.utcnow()
            store_api_access_time(self.name, 'get_balances', self.balances_time)
            balances = {symbol: Decimal(balances.get('available')) for symbol, balances in
                        balances_response.get('result').items()}
        except Exception as e:
            raise WrapP2PB2BError('Error getting trading balances {} Last Accessed {} Time Now {}'.format(e,
                                                                                                          last_accessed_time,
                                                                                                          datetime.utcnow()))
        self.balances = balances

        store_balances(self.name, balances)
        return

    def get_address(self, symbol):
        try:
            address = P2PB2B_ADDRESSES[symbol]
        except KeyError as e:
            raise Exception('Address not known for P2PB2B: {}'.format(symbol))
        except Exception as e:
            raise WrapP2PB2BError('Error getting address in P2PB2B: {}'.format(e))
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
            raise NotImplementedError('')
        except Exception as e:
            raise Exception('Error getting pending balances {}'.format(e))

    def trade_validity(self, price, volume):
        if not self.trade_pair:
            raise WrapP2PB2BError('Trade pair must be set')
        allowed_decimal_places = self.decimal_places
        volume_corrected = round_decimal_number(volume, allowed_decimal_places)
        result = False
        if volume > 0:
            result = True

        return result, price, volume_corrected

    def get_minimum_deposit_volume(self, currency):
        minimum_deposit_volume = MINIMUM_DEPOSIT.get(currency, 0)
        return minimum_deposit_volume


def Decimal_to_string(number, precision=20):
    return '{0:.{prec}f}'.format(
        number, prec=precision,
    ).rstrip('0').rstrip('.') or '0'


class WrapP2PB2BError(Exception):
    pass
