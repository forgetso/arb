from binance.client import Client
from web.settings import BINANCE_SECRET_KEY, BINANCE_PUBLIC_KEY
from web.lib.errors import ErrorTradePairDoesNotExist
import time
from decimal import Decimal, Context, setcontext

BITTREX_TAKER_FEE = 0.0025

BITTREX_ERROR_CODES = [
    {'success': False, 'message': 'INVALID_SIGNATURE', 'result': None, 'explanation': None},
    {"success": False, "message": "DUST_TRADE_DISALLOWED_MIN_VALUE_50K_SAT", "result": None},
    {'success': False, 'message': 'NO_API_RESPONSE', 'result': None},
    {'success': False, 'message': 'UUID_INVALID', 'result': None}
]


class binance():
    def __init__(self):

        self.api = Client(BINANCE_PUBLIC_KEY, BINANCE_SECRET_KEY)
        self.lowest_ask = None
        self.highest_bid = None
        self.name = 'binance'

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
            self.min_trade_size = Decimal(markets.get(self.name).get(trade_pair).get('min_trade_size'))
            self.min_trade_size_btc = Decimal(markets.get(self.name).get(trade_pair).get('min_trade_size_btc'))
            self.base_currency = markets.get(self.name).get(trade_pair).get('base_currency')
            self.quote_currency = markets.get(self.name).get(trade_pair).get('quote_currency')
        except AttributeError:
            raise ErrorTradePairDoesNotExist

    def order_book(self):
        order_book_dict = self.api.get_order_book(symbol=self.trade_pair)
        if order_book_dict.get('error'):
            raise (WrapBinanceError(order_book_dict.get('error')))
        self.asks = [{'price': Decimal(x[0]), 'volume': Decimal(x[1])} for x in
                     order_book_dict.get('asks', [])]
        self.lowest_ask = self.asks[0]
        self.bids = [{'price': Decimal(x[0]), 'volume': Decimal(x[1])} for x in
                     order_book_dict.get('bids', [])]
        self.highest_bid = self.bids[0]
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
                    'decimal_places': c['baseAssetPrecision'],
                    'min_trade_size': float(
                        [x.get('minQty') for x in c['filters'] if x['filterType'] == 'LOT_SIZE'][0]),
                    'min_trade_size_btc': float(
                        [x.get('minNotional') for x in c['filters'] if x['filterType'] == 'MIN_NOTIONAL'][0]),
                    'fee': float(fees_dict.get(c.get('symbol')))
                })

        return currency_pairs_list

    def get_currency_fees(self):
        fees_response = self.api.get_trade_fee()
        return {x.get('symbol'): x.get('taker') for x in fees_response.get('tradeFee')}

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
            raw_trade = self.get_order_status(result.get('symbol'), result.get('orderId'))

        if not raw_trade.get('status').upper() == 'FILLED':
            raise WrapBinanceError('{}'.format(result.get('message')))

        trade = self.format_trade(raw_trade, trade_type, trade_id)

        return trade

    def get_order_status(self, symbol, order_id):
        order_completed = False
        order_result = {}
        while not order_completed:
            order_result = self.get_order(symbol=symbol, order_id=order_id)
            print(order_result)
            if order_result['status'].upper() == 'FILLED':
                break
            time.sleep(5)

        return order_result

    def get_order(self, symbol, order_id):
        return self.api.get_order(symbol=symbol, orderId=order_id)

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
                'date': raw_trade['transactTime'],
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
        return total_commission_in_btc

    def get_pending_balances(self):
        try:
            deposit_history = self.api.get_deposit_history()
            pending_balances = {x.get('asset'): Decimal(x.get('amount')) for x in deposit_history['depositList'] if
                                x.get('status') == 0}
        except Exception as e:
            raise Exception('Error getting pending balances {}'.format(e))
        self.pending_balances = pending_balances


def Decimal_to_string(number, precision=20):
    return '{0:.{prec}f}'.format(
        number, prec=precision,
    ).rstrip('0').rstrip('.') or '0'


class WrapBinanceError(Exception):
    pass
