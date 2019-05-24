from bittrex.bittrex import Bittrex as BittrexAPI, API_V1_1, API_V2_0, ORDERTYPE_LIMIT, TIMEINEFFECT_GOOD_TIL_CANCELLED
from app.settings import BITTREX_PRIVATE_KEY, BITTREX_PUBLIC_KEY
from app.lib.errors import ErrorTradePairDoesNotExist
import time
from decimal import Decimal, Context, setcontext
from app.lib.common import get_number_of_decimal_places, round_decimal_number
from app.settings import BASE_CURRENCY
import logging
BITTREX_TAKER_FEE = 0.0025

BITTREX_ERROR_CODES = [
    {'success': False, 'message': 'INVALID_SIGNATURE', 'result': None, 'explanation': None},
    {"success": False, "message": "DUST_TRADE_DISALLOWED_MIN_VALUE_50K_SAT", "result": None},
    {'success': False, 'message': 'NO_API_RESPONSE', 'result': None},
    {'success': False, 'message': 'UUID_INVALID', 'result': None},
    {'success': False, 'message': 'CURRENCY_NOT_PROVIDED', 'result': None}
]


class bittrex():
    def __init__(self, jobqueue_id):
        api_version = API_V1_1
        self.api = BittrexAPI(BITTREX_PUBLIC_KEY, BITTREX_PRIVATE_KEY, api_version=api_version)
        self.lowest_ask = None
        self.highest_bid = None
        self.name = 'bittrex'
        self.min_trade_size_btc = Decimal(0.0005)
        self.balances = None
        self.pending_balances = None
        self.jobqueue_id = jobqueue_id

    def set_trade_pair(self, trade_pair, markets):
        try:
            self.decimal_places = markets.get(self.name).get(trade_pair).get('decimal_places')
            if self.decimal_places:
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
        order_book_dict = self.api.get_orderbook(market=self.trade_pair)
        if not order_book_dict.get('success'):
            raise (WrapBittrexError(order_book_dict.get('message')))
        self.asks = [{'price': Decimal(x['Rate']), 'volume': Decimal(x['Quantity'])} for x in
                     order_book_dict.get('result', {}).get('sell', [])]
        if len(self.asks):
            self.lowest_ask = self.asks[0]
        self.bids = [{'price': Decimal(x['Rate']), 'volume': Decimal(x['Quantity'])} for x in
                     order_book_dict.get('result', {}).get('buy', [])]
        if len(self.bids):
            self.highest_bid = self.bids[0]
        return order_book_dict

    def get_currency_pairs(self):
        # get all of their currency pairs in the format for the markets file
        currency_pairs_response = self.api.get_markets()
        currency_pairs_list = []
        for c in currency_pairs_response.get('result'):
            if c['IsActive'] and not c['IsRestricted']:
                currency_pairs_list.append({
                    'name': '-'.join([c['MarketCurrency'], c['BaseCurrency']]),
                    'trading_code': c['MarketName'],
                    'base_currency': c['MarketCurrency'],
                    'quote_currency': c['BaseCurrency'],
                    'min_trade_size': float(c['MinTradeSize']),
                    'fee': float(BITTREX_TAKER_FEE)
                })
        return currency_pairs_list

    def trade(self, trade_type, volume, price, trade_id=None):
        result = None
        if trade_type == 'buy':
            # self.upgrade_api()
            # result = self.api.trade_buy(market=self.trade_pair, order_type=ORDERTYPE_LIMIT, quantity=volume, rate=price,
            #                             time_in_effect=TIMEINEFFECT_GOOD_TIL_CANCELLED)
            result = self.api.buy_limit(market=self.trade_pair, quantity=volume, rate=price)
        elif trade_type == 'sell':
            result = self.api.sell_limit(
                market=self.trade_pair, quantity=volume, rate=price)

        if not result.get('success'):
            raise WrapBittrexError('{} Explanation: {}'.format(result.get('message'), result.get('explanation')))

        raw_trade = self.get_order_status(result.get('result', {}).get('uuid'))

        if not raw_trade.get('success'):
            raise WrapBittrexError('{} Explanation: {}'.format(result.get('message'), result.get('explanation')))

        trade = self.format_trade(raw_trade, trade_type, trade_id)

        return trade

    def upgrade_api(self):
        self.api = BittrexAPI(BITTREX_PUBLIC_KEY, BITTREX_PRIVATE_KEY, api_version=API_V2_0)

    def get_order_status(self, order_id):
        order_completed = False
        order_result = {}
        while not order_completed:
            order_result = self.get_order(order_id=order_id)
            if order_result['result']['IsOpen'] is False:
                break
            time.sleep(2)

        return order_result

    def get_order(self, order_id):
        return self.api.get_order(uuid=order_id)

    def format_trade(self, raw_trade, trade_type, trade_id):

        # {'success': True,
        # 'message': '',
        # 'result':
        # {'AccountId': None, 'OrderUuid': '544f0b9f-b6c2-43f3-a588-1ed5ec3f6714', 'Exchange': 'BTC-ETH',
        # 'Type': 'LIMIT_BUY', 'Quantity': 0.0191356, 'QuantityRemaining': 0.0, 'Limit': 0.0261293,
        # 'Reserved': 0.00049999, 'ReserveRemaining': 0.00049999, 'CommissionReserved': 1.24e-06,
        # 'CommissionReserveRemaining': 0.0, 'CommissionPaid': 1.24e-06, 'Price': 0.00049999,
        # 'PricePerUnit': 0.02612878, 'Opened': '2018-12-12T15:25:36.887',
        # 'Closed': '2018-12-12T15:25:37.12', 'IsOpen': False,
        # 'Sentinel': '0e39edb7-20b4-454f-aeed-c7c39b1ebe54', 'CancelInitiated': False, 'ImmediateOrCancel': False,
        # 'IsConditional': False, 'Condition': 'NONE', 'ConditionTarget': None}}

        try:
            trade = {
                'external_id': raw_trade['result']['OrderUuid'],
                '_id': str(trade_id),
                'status': 'Closed',
                'trade_pair_common': self.trade_pair_common,
                'trade_pair': self.trade_pair,
                'trade_type': trade_type,
                'price': raw_trade['result']['PricePerUnit'],
                'volume': raw_trade['result']['Quantity'],
                'trades_itemised': [],
                'date': raw_trade['result']['Closed'],
                'fees': raw_trade['result']['CommissionPaid'],
                'exchange': self.name
            }
        except Exception as e:
            raise WrapBittrexError('Error formatting trade {}'.format(e))

        return trade

    def get_balances(self):
        try:
            balances = {x.get('Currency'): x.get('Available') for x in self.api.get_balances().get('result', {})}
        except Exception as e:
            raise Exception('Error getting trading balances {}'.format(e))
        self.balances = balances

    def get_address(self, symbol):
        try:
            address_json = self.api.get_deposit_address(currency=symbol)
            address = address_json.get('result').get('Address')
        except Exception as e:
            raise Exception('Error getting currency address {}'.format(e))
        return address

    def get_pending_balances(self):
        try:
            balances = {x.get('Currency'): x.get('Pending') for x in self.api.get_balances().get('result', {})}
        except Exception as e:
            raise Exception('Error getting trading balances {}'.format(e))
        self.pending_balances = balances

    # currently withdraw is only implemented for bittrex
    def withdraw(self, currency, to_address, quantity):
        withdrawn = False
        withdraw_response = self.api.withdraw(currency, quantity, to_address)
        if not withdraw_response.get('success'):
            if withdraw_response.get('message') != 'INSUFFICIENT_FUNDS':
                raise WrapBittrexError('Error withdrawing {}'.format(withdraw_response.get('message')))
        else:
            withdrawn = True
        return withdrawn

    def trade_validity(self, price, volume):
        if not self.trade_pair:
            raise WrapBittrexError('Trade pair must be set')
        allowed_decimal_places = get_number_of_decimal_places(self.min_trade_size)
        volume_corrected = round_decimal_number(volume, allowed_decimal_places)

        # if price * volume < self.min_trade_size_btc:
        #     volume = self.min_trade_size_btc / price
        result = False
        # finally, check if the volume we're attempting to trade is above the minimum notional trade size
        if volume_corrected > self.min_trade_size:
            result = True

        # this is an extra check to make sure that the trade size is bigger than the smallest trade size allowed in BTC
        if self.quote_currency == BASE_CURRENCY:
            if price * volume_corrected > self.min_trade_size_btc:
                result = True
            else:
                result = False

        # TODO work out if non BASE CURRENCY trades are above the BASE_CURRENCY threshold, for example ETH-LTC
        if self.quote_currency != BASE_CURRENCY:
            #raise NotImplementedError('Cannot check if {} trade meets minimum requirements'.format(self.name))
            logging.warning('Cannot determine if trade meets minimum BTC trade requirements')
            result = True

        return result, price, volume_corrected


class WrapBittrexError(Exception):
    pass
