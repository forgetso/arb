import gatecoin_api as gapi
import json
from web.settings import GATECOIN_PUBLIC_KEY, GATECOIN_PRIVATE_KEY, LOGLEVEL
from web.lib.errors import ErrorTradePairDoesNotExist
import logging
import time
from gatecoin_api.request import Request
from decimal import Decimal, Context, setcontext
from web.lib.common import round_decimal_number

GATECOIN_TAKER_FEE = 0.0035

GATECOIN_ERROR_CODES = [
    {'cl_order_id': None, 'order_status': None,
     'response_status': {'error_code': '1005', 'message': 'Insufficient funds', 'stack_trace': None, 'errors': None}},
    {'cl_order_id': None, 'order_status': None,
     'response_status': {'error_code': '1004', 'message': 'At least one property must be greater than 0',
                         'stack_trace': None, 'errors': [{'error_code': '1004', 'field_name': 'Amount, SpendAmount',
                                                          'message': 'At least one property must be greater than 0'}]}},
    {'cl_order_id': None, 'order_status': None,
     'response_status': {'error_code': '1004', 'message': 'Amount too small', 'stack_trace': None,
                         'errors': [{'error_code': '1004', 'field_name': 'Amount', 'message': 'Amount too small'}]}}

]


class gatecoin():
    def __init__(self):
        self.api = gapi.GatecoinAPI(public_key=GATECOIN_PUBLIC_KEY, private_key=GATECOIN_PRIVATE_KEY)
        self.lowest_ask = None
        self.highest_bid = None
        self.name = 'gatecoin'
        self.balances = {}
        logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)

    def set_trade_pair(self, trade_pair, markets):
        try:
            self.decimal_places = markets.get(self.name).get(trade_pair).get('decimal_places')
            if self.decimal_places:
                self.decimal_places = Decimal(self.decimal_places)
                decimal_rounding_context = Context(prec=int(self.decimal_places))
                setcontext(decimal_rounding_context)
            self.price_decimal_places = markets.get(self.name).get(trade_pair).get('price_decimal_places')
            self.trade_pair_common = trade_pair
            self.trade_pair = markets.get(self.name).get(trade_pair).get('trading_code')
            self.fee = Decimal(markets.get(self.name).get(trade_pair).get('fee'))
            self.base_currency = markets.get(self.name).get(trade_pair).get('base_currency')
            self.quote_currency = markets.get(self.name).get(trade_pair).get('quote_currency')
        except AttributeError:
            raise ErrorTradePairDoesNotExist

    def order_book(self):
        order_book = str(self.api.get_order_book(self.trade_pair)).replace("'", '"')
        order_book_dict = json.loads(order_book)
        self.asks = order_book_dict.get('asks')
        if len(self.asks):
            self.lowest_ask = {'price': Decimal(self.asks[0]['price']), 'volume': Decimal(self.asks[0]['volume'])}

        self.bids = order_book_dict.get('bids')
        if len(self.bids):
            self.highest_bid = {'price': Decimal(self.bids[0]['price']), 'volume': Decimal(self.bids[0]['volume'])}

        return order_book_dict

    def get_currency_pairs(self):
        # this just prints all of their currency pairs in the format for the markets file
        currency_pairs_response = self.api.get_currency_pairs()
        currency_pairs_list = []

        for c in currency_pairs_response.currency_pairs:
            currency_pairs_list.append({
                'name': '-'.join([c.base_currency, c.quote_currency]),
                'trading_code': c.trading_code,
                'base_currency': c.base_currency,
                'quote_currency': c.quote_currency,
                'price_decimal_places': c.price_decimal_places,
                # TODO store both maker and taker fee
                'fee': GATECOIN_TAKER_FEE
            })
        return currency_pairs_list

    def trade(self, trade_type, volume, price, trade_id=None):
        order_way = None
        trade = None
        if trade_type == 'buy':
            order_way = 'Bid'
        elif trade_type == 'sell':
            order_way = 'Ask'
        if order_way:
            result = self.api.create_order(currency_pair=self.trade_pair, order_way=order_way, price=price,
                                           amount=volume)
            if result.response_status.errors:
                raise WrapGatecoinError(
                    '{} : {}'.format(result.response_status.error_code, result.response_status.message))
            else:

                if not result.order_status:
                    # wait until the order is completed
                    result = self.get_order_status(result.cl_order_id)

                trade = self.format_trade(result)

        return trade

    def get_order_status(self, order_id):
        order_completed = False
        result = None
        while not order_completed:
            result = self.get_order(order_id=order_id)
            if result.order.status == 6 and result.order.remaining_quantity == 0.0:
                break
            time.sleep(2)

        return result.order

    def get_order(self, order_id):
        return self.api.get_open_order(order_id=order_id)

    def format_trade(self, raw_trade, trade_type, trade_id):
        # Incomplete Order
        # {'cl_order_id': 'BK11607863190', 'order_status': None, 'response_status': {'error_code': None, 'message': 'OK', 'stack_trace': None, 'errors': None}}
        #
        # Complete Order
        # {'code': 'ETHBTC', 'cl_order_id': 'BK11607863836', 'side': 0, 'price': 0.0284, 'initial_quantity': 0.00035211,
        #  'remaining_quantity': 0.0, 'status': 6, 'status_desc': 'Executed', 'transaction_sequence_number': None,
        #  'type': 0, 'date': datetime.datetime(2018, 12, 2, 22, 40, 48, tzinfo=tzutc()), 'trades': None}

        try:
            trade = {
                'external_id': raw_trade.cl_order_id,
                '_id': trade_id,
                'status': raw_trade.order_status,
                'trade_pair_common': self.trade_pair_common,
                'trade_pair': self.trade_pair,
                'trade_type': trade_type,
                'price': raw_trade.price,
                'volume': raw_trade.initial_quantity,
                'trades_itemised': raw_trade.trades,
                'date': raw_trade.date,
                'exchange': self.name
            }
        except Exception as e:
            raise Exception('Error formatting trade {}'.format(e))

    def get_balances(self):
        # try:
        balances = {x.currency: x.available_balance for x in self.api.get_balances().balances}
        # except Exception as e:
        #     raise Exception('Error getting trading balances {}'.format(e))
        self.balances = balances

    def get_address(self, symbol):
        try:
            address = None
            # this method is not implemented in the gatecoin pip package
            # https://api.gatecoin.com/v1/ElectronicWallet/DepositWallets/{DigiCurrency}
            gatecoin_request = Request(private_key=GATECOIN_PRIVATE_KEY,
                                       public_key=GATECOIN_PUBLIC_KEY,
                                       command='v1/ElectronicWallet/DepositWallets/{}'.format(symbol.upper()),
                                       )
            response = gatecoin_request.send()
            addresses = response.get('addresses')
            if addresses:
                address = addresses[0].get('address')
        except Exception as e:
            raise WrapGatecoinError('Error getting currency address {}'.format(e))
        return address

    def get_pending_balances(self):
        try:
            # this method is not implemented in the gatecoin pip package
            # https://api.gatecoin.com/v1/Balance/Deposits
            gatecoin_request = Request(private_key=GATECOIN_PRIVATE_KEY,
                                       public_key=GATECOIN_PUBLIC_KEY,
                                       command='v1/Balance/Deposits')

            response = gatecoin_request.send()
            pending_balances = {x.get('currency'): Decimal(x.get('amount')) for x in response['digiTransfers'] if
                                x.get('status') == 'Pending'}
        except Exception as e:
            raise WrapGatecoinError('Error getting pending balances {}'.format(e))
        self.pending_balances = pending_balances

    def trade_validity(self, price, volume):
        if not self.trade_pair:
            raise WrapGatecoinError('Trade pair must be set')
        allowed_decimal_places = self.decimal_places
        price_corrected = round_decimal_number(price, allowed_decimal_places)
        result = True
        return result, price_corrected, volume


class WrapGatecoinError(Exception):
    pass
