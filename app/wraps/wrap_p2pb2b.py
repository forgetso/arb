from p2pb2bapi import P2PB2B
from app.settings import P2PB2B_SECRET_KEY, P2PB2B_PUBLIC_KEY
from decimal import Decimal
from app.lib.db import store_balances, get_balances, store_api_access_time, get_api_access_time, lock_api_method, \
    unlock_api_method, get_api_method_lock, get_minutely_api_requests, get_secondly_api_requests
import logging
from datetime import datetime, timedelta
import time
from app.lib.exchange import exchange

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
    'LTC': 'MTwXbS618hG2TiseGd3axe37ibjdHAj3pd'
}


class p2pb2b(exchange):
    def __init__(self, jobqueue_id):

        self.api = P2PB2B(P2PB2B_PUBLIC_KEY, P2PB2B_SECRET_KEY)
        self.lowest_ask = None
        self.highest_bid = None
        self.name = 'p2pb2b'
        self.balances = None
        self.balances_time = None
        self.jobqueue_id = jobqueue_id
        self.minimum_deposit = MINIMUM_DEPOSIT
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
        self.api = P2PB2B(P2PB2B_PUBLIC_KEY, P2PB2B_SECRET_KEY)

    def order_book(self):
        # TODO put rate limiting in for this wrapper at the very beginning. Store the number of API hits that have occurred in the current minute and second
        # limit is 5 per second or 100 per minute
        order_book_dict = {}
        ticker_buy_response = None
        if get_minutely_api_requests(self.name) < P2PB2B_API_RATE_LIMIT_MINUTELY and get_secondly_api_requests(
                self.name) < P2PB2B_API_RATE_LIMIT_SECONDLY:
            try:
                ticker_buy_response = self.api.getBook(market=self.trade_pair, side='buy', limit=10)
            except Exception as e:
                raise WrapP2PB2BError('Error getting order book from p2pb2b: {}'.format(e))
            store_api_access_time(self.name, 'order_book', datetime.utcnow())
            if not ticker_buy_response.get('success'):
                print(ticker_buy_response)
                raise WrapP2PB2BError(
                    'Error getting order book for {} : {}'.format(self.trade_pair,
                                                                  ticker_buy_response.get('message')))

            order_book_dict['buy'] = ticker_buy_response.get('result')
            try:
                ticker_sell_response = self.api.getBook(market=self.trade_pair, side='sell', limit=10)
            except Exception as e:
                raise WrapP2PB2BError('Error getting order book from p2pb2b: {}'.format(e))
            store_api_access_time(self.name, 'order_book', datetime.utcnow())
            if not ticker_sell_response.get('success'):
                raise WrapP2PB2BError(
                    'Error getting order book for {} : {}'.format(self.trade_pair, ticker_sell_response.get('message')))
            order_book_dict['sell'] = ticker_sell_response.get('result')

            # ticker contains lowest ask and highest bid. we will only use this info as we currently don't care about other bids
            # we take the volume from left as this is how much of this trade is left until it completes
            self.asks = [{'price': Decimal(x['price']), 'volume': Decimal(x['left'])} for x in
                         order_book_dict['sell']['orders']]
            self.lowest_ask = self.asks[0]
            self.bids = [{'price': Decimal(x['price']), 'volume': Decimal(x['left'])} for x in
                         order_book_dict['buy']['orders']]
            self.highest_bid = self.bids[0]
            logging.debug(
                'p2pb2b lowest ask {} highest bid {}'.format(self.lowest_ask['price'], self.highest_bid['price']))
            # return_value_to_stdout(self.__getstate__())

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
                    # TODO better method of identifying base and quote currency
                    'base_currency': symbol_split[0],
                    'quote_currency': symbol_split[1],
                    'decimal_places': int(c.get('stockPrec')),
                    'decimal_places_base': int(c.get('moneyPrec')),
                    'min_trade_size': float(c.get('minAmount')),
                    'min_trade_size_currency': symbol_split[0],
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
        order_id = result.get('orderId')
        raw_trade = {}
        waits = 0
        while not raw_trade:
            raw_trade = self.get_order_status(order_id)
            time.sleep(20)
            waits += 1
            if waits > 6:
                raise WrapP2PB2BError('Trade not executed after 2 minutes: ID {}'.format(order_id))

        trade = self.format_trade(raw_trade, trade_type, trade_id)

        return trade

    def get_order_status(self, order_id):
        order_result = {}
        order_response = self.get_order(order_id=order_id)
        success = order_response.get('success')

        if not success:
            raise WrapP2PB2BError(order_response.get('message'))

        if success and order_response.get('result')['records']:
            order_result = order_response['result']

        return order_result

    def get_order(self, order_id):
        # try:
        order = self.api.getOrder(order_id)
        # except Exception as e:
        #     raise WrapP2PB2BError('Error retrieving order: {} {}'.format(order_id, e))

        return order

    def get_orders(self, order_id):
        raise NotImplementedError('Get Orders not implemented in P2PB2B Wrapper')

    def format_trade(self, raw_trade, trade_type, trade_id):
        # {
        #     "success": true,
        #     "message": "",
        #     "result": {
        #         "offset": 0,
        #         "limit": 50,
        #         "records": [
        #             {
        #                 "time": 1533310924.935978,
        #                 "fee": "0",
        #                 "price": "80.22761599",
        #                 "amount": "2.12687945",
        #                 "id": 548,
        #                 "dealOrderId": 1237,
        #                 "role": 1,
        #                 "deal": "170.6344677716224055"
        #             }
        #         ]
        #     }
        # }

        try:
            trade = {
                'external_id': raw_trade['records'][0]['dealOrderId'],
                '_id': str(trade_id),
                'status': 'Closed',
                'trade_pair_common': self.trade_pair_common,
                'trade_pair': self.trade_pair,
                'trade_type': trade_type,
                'price': Decimal(raw_trade['records'][0]['price']),
                'volume': Decimal(raw_trade['records'][0]['amount']),
                'trades_itemised': raw_trade['records'],
                'date': datetime.fromtimestamp(raw_trade['records'][0]['time']),
                'fees': Decimal(raw_trade['records'][0]['fee']),
                'exchange': self.name
            }
        except Exception as e:
            raise WrapP2PB2BError('Error formatting trade {} {}'.format(e, raw_trade))

        return trade

    def get_balances(self):
        last_accessed_time = get_api_access_time(self.name, 'get_balances')
        # this api has limits so we've stored the balances in the database in case of querying too frequently
        # fingers crossed they are correct !
        logging.debug('Last accessed time {}'.format(last_accessed_time))
        # if we know when we last accessed balances and that time was less than 60s ago then we get balances from the db
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
        # TODO check with P2PB2B to see if this is definitely the case
        raise NotImplementedError('P2PB2B does not provide a pending balances API call')


class WrapP2PB2BError(Exception):
    pass
