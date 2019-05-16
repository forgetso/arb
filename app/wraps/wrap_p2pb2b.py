from p2pb2bapi import P2PB2B
from app.settings import P2PB2B_SECRET_KEY, P2PB2B_PUBLIC_KEY
from app.lib.errors import ErrorTradePairDoesNotExist
from decimal import Decimal, Context, setcontext
from app.lib.common import round_decimal_number, get_number_of_decimal_places
from app.lib.db import store_balances, get_balances, store_api_access_time, get_api_access_time, lock_api_method, \
    unlock_api_method, get_api_method_lock
import logging
from datetime import datetime
import time

P2PB2B_TAKER_FEE = 0.0020
P2PB2B_MAKER_FEE = 0.0020

P2PB2B__ERROR_CODES = []

# TODO work out a way of automatically importing addresses
P2PB2B_ADDRESSES = {
    'BTC': '3MBYPQNeAL9L6dSEFkG6AfmyMycoMjsJYV',
    'ETH': '0x6cA28a73b125b3F1C3760673AacE15A1EF9c3C90',
    # 'BNB': '0x1c6FEF78ccd5FEDaf580e09695322ea699377b87',
    'ETC': '0xAF58C3C4383611Ab84581D7A59B4Bf84C07D58Dd',
    'LTC': 'MRbqHQmaf1zhKUZ3MRkxQ5yQqKjSgyfYuF',
    # 'WAVES': '3PNr7xxDCUcaLZ6yrfd9DJs6AbQYQzeeXSM',
    # 'BTG': 'GYi8938gZXjeXJmeDwP9rY7ofm51gLjq49',
    # 'XLM': 'GB347U2XAKGGGUVJMWMVW5YVXPF66RNQISPJAFWUIZKV3PNJL75WXCF7',
    # 'BCH': 'bitcoincash:qrugdfq28f03upz7uadga04skzah3zet7qxqcwsayk',
    # 'DOGE': 'DT9QUoJ2Zbd91USWrPuUzijF3SDEhR9w3y',
    # 'TUSD': '0xCD470e2c03E3DB140aB22e89244dA600a6Cb0c88',
    # 'PAX': '0x54763C9c531192Ea53E66b51c71E9b02fbb0d838',
    # 'NEO': 'AMmm8hg3xR8BGpp1WZvs8Zu6rG2Xqxz1M7',
    # 'DASH': 'Xej5dEvap2iVeCXShGy9iri7T3mQkEN6Ku',
    # 'GAS': 'AGaef46GedPJV7uBTFEfgvUN68Evxr9b6T',

}


class p2pb2b():
    def __init__(self):

        self.api = P2PB2B(P2PB2B_PUBLIC_KEY, P2PB2B_SECRET_KEY)
        self.lowest_ask = None
        self.highest_bid = None
        self.name = 'p2pb2b'
        self.balances = None
        self.balances_time = None

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
        order_book_dict = {}
        ticker_buy_response = None
        ticker_buy_response = self.api.getBook(market=self.trade_pair, side='buy', limit=1)
        if not ticker_buy_response.get('success'):
            raise WrapP2PB2BError(
                'Error getting order book for {} : {}, {}'.format(self.trade_pair, ticker_buy_response.get('message'),
                                                                  ticker_buy_response))
        order_book_dict['buy'] = ticker_buy_response.get('result')
        ticker_sell_response = self.api.getBook(market=self.trade_pair, side='sell', limit=1)
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
        if trade_type == 'buy':
            result = self.api.order_limit_buy(symbol=self.trade_pair, quantity=volume, price=price)
        elif trade_type == 'sell':
            result = self.api.order_limit_sell(symbol=self.trade_pair, quantity=volume, price=price)

        if not result.get('status'):
            raise WrapP2PB2BError('{}'.format(result.get('message')))

        if result.get('status').upper() == 'FILLED':
            raw_trade = result
        else:
            raw_trade = self.get_order_status(result.get('symbol'), result.get('orderId'))

        if not raw_trade.get('status').upper() == 'FILLED':
            raise WrapP2PB2BError('{}'.format(result.get('message')))

        trade = self.format_trade(raw_trade, trade_type, trade_id)

        return trade

    def get_order_status(self, symbol, order_id):
        order_completed = False
        order_result = {}
        while not order_completed:
            order_result = self.get_order(symbol=symbol, order_id=order_id)
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
        # TODO check that the balances were last retrieved within a reasonable timeframe (TBC)
        logging.debug('Last accessed time {}'.format(last_accessed_time))
        if self.balances_time and time.time() - self.balances_time < 30 or time.time() - last_accessed_time < 30:
            balances = get_balances(self.name)
            self.balances = balances
            logging.debug('p2pb2b balances already retrieved')
            return

        wait_count = 0
        while get_api_method_lock(self.name, 'get_balances'):
            time.sleep(5)
            wait_count += 1
            if wait_count > 4:
                logging.warning('API method "get_balances" has been locked for more than 20s')
                return

        try:

            lock_api_method(self.name, 'get_balances')
            balances_response = self.api.getBalances()
            if not balances_response.get('success'):
                raise Exception(balances_response.get('message'))
            unlock_api_method(self.name, 'get_balances')
            self.balances_time = time.time()
            store_api_access_time(self.name, 'get_balances', self.balances_time)
            balances = {symbol: Decimal(balances.get('available')) for symbol, balances in
                        balances_response.get('result').items()}
        except Exception as e:
            raise WrapP2PB2BError('Error getting trading balances {} Last Accessed {} Time Now {}'.format(e,
                                                                                                          datetime.fromtimestamp(
                                                                                                              last_accessed_time),
                                                                                                          datetime.utcnow()))
        self.balances = balances

        store_balances(self.name, balances)
        return

    def get_address(self, symbol):
        try:
            address_json = P2PB2B_ADDRESSES[symbol]
        except Exception as e:
            raise Exception('Error getting currency address in P2P {}'.format(e))
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
            raise NotImplementedError('')
        except Exception as e:
            raise Exception('Error getting pending balances {}'.format(e))

    def trade_validity(self, price, volume):
        if not self.trade_pair:
            raise WrapP2PB2BError('Trade pair must be set')
        allowed_decimal_places = self.decimal_places
        volume_corrected = round_decimal_number(volume, allowed_decimal_places)
        result = False

        return result, price, volume_corrected


def Decimal_to_string(number, precision=20):
    return '{0:.{prec}f}'.format(
        number, prec=precision,
    ).rstrip('0').rstrip('.') or '0'


class WrapP2PB2BError(Exception):
    pass