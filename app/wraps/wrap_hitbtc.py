from app.lib.hitbtcapi import Client as HitBTCClient
from app.settings import HITBTC_PUBLIC_KEY, HITBTC_SECRET_KEY
from decimal import Decimal, Context, setcontext
from app.lib.errors import ErrorTradePairDoesNotExist
import uuid
import logging
from app.settings import LOGLEVEL
from app.lib.common import get_number_of_decimal_places, round_decimal_number
from app.lib.exchange import exchange

URL = 'https://api.hitbtc.com'

HITBTC_ERROR_CODES = {
    400: [
        {'error': {'code': 20001, 'message': 'Insufficient funds',
                   'description': 'Check that the funds are sufficient, given commissions'}},
        {'error': {'code': 2011, 'message': 'Quantity too low', 'description': 'Minimum quantity 0.0001'}}
    ]
}

MINIMUM_DEPOSIT = {}


class hitbtc(exchange):
    def __init__(self, jobqueue_id):
        self.api = HitBTCClient(public_key=HITBTC_PUBLIC_KEY, secret=HITBTC_SECRET_KEY, url=URL)
        self.lowest_ask = None
        self.highest_bid = None
        self.name = 'hitbtc'
        self.balances = {}
        self.pending_balances = {}
        self.jobqueue_id = jobqueue_id
        # self.min_trade_size_btc = Decimal(0.0001)
        logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)
        exchange.__init__(self, name=self.name, jobqueue_id=jobqueue_id)

    def order_book(self):
        order_book_dict = self.api.get_orderbook(self.trade_pair)
        asks_raw = order_book_dict.get('ask', [])
        self.asks = [{'price': Decimal(x['price']), 'volume': Decimal(x['size'])} for x in asks_raw]
        if len(self.asks):
            self.lowest_ask = self.asks[0]
        bids_raw = order_book_dict.get('bid', [])
        self.bids = [{'price': Decimal(x['price']), 'volume': Decimal(x['size'])} for x in bids_raw]
        if len(self.bids):
            self.highest_bid = self.bids[0]
        logging.debug(
            'Hitbtc lowest ask {} highest bid {}'.format(self.lowest_ask['price'], self.highest_bid['price']))
        return order_book_dict

    def get_currencies(self, symbol=None):
        currencies_response = self.api.get_currency(symbol)
        return currencies_response

    def get_currency_pairs(self):
        # first ignore all currencies that have either deposits or withdrawals suspended
        ignore = [x['id'] for x in self.get_currencies() if
                  x['delisted'] or not x['payoutEnabled'] or not x['payinEnabled']]

        # this just prints all of their currency pairs in the format for the markets file
        currency_pairs_response = self.api.get_symbol('')
        currency_pairs_list = []

        for c in currency_pairs_response:
            if c['baseCurrency'] not in ignore and c['quoteCurrency'] not in ignore:
                currency_pairs_list.append({
                    'name': '-'.join([c['baseCurrency'], c['quoteCurrency']]),
                    'trading_code': c['id'],
                    'base_currency': c['baseCurrency'],
                    'quote_currency': c['quoteCurrency'],
                    'decimal_places': -Decimal(c['tickSize']).as_tuple().exponent,
                    'min_trade_size': float(c['quantityIncrement']),
                    'min_trade_size_currency': c['baseCurrency'],
                    'fee': float(c['takeLiquidityRate'])
                })
        return currency_pairs_list

    def trade(self, trade_type, volume, price, trade_id=None):
        result = None
        if not trade_id:
            trade_id = uuid.uuid4()
        if trade_type == 'buy' or trade_type == 'sell':
            result = self.api.new_order(client_order_id=trade_id, symbol_code=self.trade_pair, side=trade_type,
                                        quantity=volume,
                                        price=price)

        # trade format
        # TRADE_SUCCESS = {'id': '79188782732', 'clientOrderId': 'd449ed67d4c74136b52d140114142ed1', 'symbol': 'ETHBTC',
        #                  'side': 'buy', 'status': 'filled', 'type': 'limit', 'timeInForce': 'GTC', 'quantity': '0.001',
        #                  'price': '0.028027', 'cumQuantity': '0.001', 'createdAt': '2018-12-02T21:34:30.901Z',
        #                  'updatedAt': '2018-12-02T21:34:30.901Z', 'postOnly': False, 'tradesReport': [
        #         {'id': 410034353, 'quantity': '0.001', 'price': '0.028027', 'fee': '0.000000029',
        #          'timestamp': '2018-12-02T21:34:30.901Z'}]}

        trade = self.format_trade(raw_trade=result, trade_type=trade_type, trade_id=trade_id)

        return trade

    def format_trade(self, raw_trade, trade_type, trade_id):
        trade = None
        try:
            trade = {
                'external_id': raw_trade.get('id'),
                '_id': trade_id,
                'status': raw_trade.get('status'),
                'trade_pair_common': self.trade_pair_common,
                'trade_pair': self.trade_pair,
                'trade_type': trade_type,
                'price': raw_trade.get('price'),
                'volume': raw_trade.get('cumQuantity'),
                'trades_itemised': raw_trade.get('tradesReport', []),
                'exchange': self.name
            }
        except Exception as e:
            raise WrapHitBtcError('Error formatting trade {}'.format(e))

        return trade

    def get_balances(self):
        try:
            balances = {x.get('currency'): Decimal(x.get('available')) for x in self.api.get_trading_balance()}
        except Exception as e:
            raise WrapHitBtcError('Error getting trading balances {}'.format(e))
        self.balances = balances

    def get_address(self, symbol):
        try:
            address_json = self.api.get_address(currency_code=symbol)
        except Exception as e:
            raise WrapHitBtcError('Error getting currency address in HitBtc {}'.format(e))
        return address_json.get('address')

    def get_pending_balances(self):
        try:
            transactions = self.api.get_transactions()
            pending_balances = {x.get('currency'): Decimal(x.get('amount')) for x in transactions if
                                x.get('status') == 'pending' and x.get('type') == 'payin'}
        except Exception as e:
            raise Exception('Error getting pending balances in HitBtc {}'.format(e))
        self.pending_balances = pending_balances

    def get_orders(self, order_id):
        raise NotImplementedError('Get Orders not implemented in HitBTC Wrapper')

    def get_order(self, order_id):
        raise NotImplementedError('Get Order not implemented in HitBTC Wrapper')

    def calculate_fees(self, trades_itemised, price):
        raise NotImplementedError('Calculate Fees not implemented in HitBTC Wrapper')

    def get_order_status(self, order_id):
        raise NotImplementedError('Get Order Status not implemented in HitBTC Wrapper')


class WrapHitBtcError(Exception):
    pass
