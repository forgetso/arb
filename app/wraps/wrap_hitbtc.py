from app.lib.hitbtcapi import Client as HitBTCClient
from app.settings import HITBTC_PUBLIC_KEY, HITBTC_SECRET_KEY
from decimal import Decimal, Context, setcontext
from app.lib.errors import ErrorTradePairDoesNotExist
import uuid
import logging
from app.settings import LOGLEVEL
from app.lib.common import get_number_of_decimal_places, round_decimal_number

URL = 'https://api.hitbtc.com'

HITBTC_ERROR_CODES = {
    400: [
        {'error': {'code': 20001, 'message': 'Insufficient funds',
                   'description': 'Check that the funds are sufficient, given commissions'}},
        {'error': {'code': 2011, 'message': 'Quantity too low', 'description': 'Minimum quantity 0.0001'}}
    ]
}


class hitbtc:
    def __init__(self):
        self.api = HitBTCClient(public_key=HITBTC_PUBLIC_KEY, secret=HITBTC_SECRET_KEY, url=URL)
        self.lowest_ask = None
        self.highest_bid = None
        self.name = 'hitbtc'
        self.balances = {}
        self.pending_balances = {}
        # self.min_trade_size_btc = Decimal(0.0001)
        logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)

    def set_trade_pair(self, trade_pair, markets):
        try:
            self.decimal_places = markets.get(self.name).get(trade_pair).get('decimal_places')
            if self.decimal_places:
                # denominator_str = '1e{}'.format(self.decimal_places)
                self.decimal_places = Decimal(self.decimal_places)
                decimal_rounding_context = Context(prec=int(self.decimal_places))
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
        order_book_dict = self.api.get_orderbook(self.trade_pair)
        self.asks = order_book_dict.get('ask', [])
        if len(self.asks):
            self.lowest_ask = {'price': Decimal(self.asks[0]['price']), 'volume': Decimal(self.asks[0]['size'])}
        self.bids = order_book_dict.get('bid', [])
        if len(self.bids):
            self.highest_bid = {'price': Decimal(self.bids[0]['price']), 'volume': Decimal(self.bids[0]['size'])}
        return order_book_dict

    def get_currency_pairs(self):
        # this just prints all of their currency pairs in the format for the markets file
        currency_pairs_response = self.api.get_symbol('')
        currency_pairs_list = []
        for c in currency_pairs_response:
            currency_pairs_list.append({
                'name': '-'.join([c['baseCurrency'], c['quoteCurrency']]),
                'trading_code': c['id'],
                'base_currency': c['baseCurrency'],
                'quote_currency': c['quoteCurrency'],
                'decimal_places': -Decimal(c['tickSize']).as_tuple().exponent,
                'min_trade_size': float(c['quantityIncrement']),
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

    def trade_validity(self, price, volume):
        if not self.trade_pair:
            raise WrapHitBtcError('Trade pair must be set')
        result = False
        volume_corrected = 0

        if volume > 0:

            # takes the decimal part of the minimum trade size and inverts it, giving the number of decimal places
            logging.debug('Min Trade Size HitBtc {}'.format(self.min_trade_size))
            allowed_decimal_places = get_number_of_decimal_places(self.min_trade_size)
            volume_corrected = round_decimal_number(volume, allowed_decimal_places)

            if volume_corrected > self.min_trade_size:
                result = True

        return result, price, volume_corrected


class WrapHitBtcError(Exception):
    pass
