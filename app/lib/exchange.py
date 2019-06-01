from abc import ABC, abstractmethod
from app.lib.errors import ErrorTradePairDoesNotExist
from decimal import Decimal, setcontext, Context
from app.lib.common import get_number_of_decimal_places, round_decimal_number
import logging
from app.settings import DEFAULT_CURRENCY


# this abstract class contains all of the methods that an exchange wrap must implement

class exchange(ABC):
    def __init__(self, name, jobqueue_id):
        self.jobqueue_id = jobqueue_id
        self.name = name  # this is set by the inheriting class
        self.trade_pair = None
        self.trade_pair_common = None
        self.lowest_ask = None
        self.asks = None
        self.highest_bid = None
        self.bids = None
        self.fee = None
        self.min_trade_size = None
        self.min_trade_size_currency = None
        self.base_currency = None
        self.quote_currency = None

        super().__init__()

    def set_trade_pair(self, trade_pair, markets):
        try:
            if not self.name:
                raise ValueError('Exchange must have name attribute set')
            trade_pair_details = markets.get(self.name).get(trade_pair)
            self.decimal_places = int(self.decimal_places)
            decimal_rounding_context = Context(prec=self.decimal_places)
            setcontext(decimal_rounding_context)
            self.trade_pair_common = trade_pair
            self.trade_pair = trade_pair_details.get('trading_code')
            self.fee = Decimal(trade_pair_details.get('fee'))
            self.min_trade_size = Decimal(str(trade_pair_details.get('min_trade_size')))
            self.min_trade_size_currency = trade_pair_details.get('min_trade_size_currency')
            self.base_currency = trade_pair_details.get('base_currency')
            self.quote_currency = trade_pair_details.get('quote_currency')
        except AttributeError:
            raise ErrorTradePairDoesNotExist

    @abstractmethod
    def order_book(self):
        pass

    @abstractmethod
    def get_currency_pairs(self):
        pass

    @abstractmethod
    def trade(self, trade_type, volume, price, trade_id=None):
        pass

    @abstractmethod
    def get_order_status(self, order_id):
        pass

    @abstractmethod
    def get_order(self, order_id):
        pass

    @abstractmethod
    def format_trade(self, raw_trade, trade_type, trade_id):
        pass

    @abstractmethod
    def get_balances(self):
        pass

    @abstractmethod
    def get_address(self, symbol):
        pass

    @abstractmethod
    def calculate_fees(self, trades_itemised, price):
        pass

    @abstractmethod
    def get_pending_balances(self):
        pass

    # Takes a price and a volume for a currency on the exchange
    # 1. The volume is rounded to the allowed number of decimal places for the exchange
    # The volume * price then gives the trade size in the quote currency (usually ETH or BTC)
    # A minimum trade size can be quoted in either ETH or BTC so we need to check one of
    # 2. volume > minimum trade size in Base Currency
    # 3. volume * price > minimum trade size in Quote Currency

    # ********************************** Definition *************************************
    # The quotation EUR/USD 1.2500 means that one euro is exchanged for 1.2500 US dollars.
    # Here, EUR is the base currency and USD is the quote currency(counter currency).
    def trade_validity(self, currency, price, volume):
        result = False
        if not self.trade_pair:
            raise ExchangeError('Trade pair must be set')

        if not isinstance(price, Decimal) or not isinstance(volume, Decimal):
            raise TypeError(
                '{} trade_validity: Price and Volume must be type Decimal. Not {} or {}'.format(self.name, type(price),
                                                                                                type(volume)))

        volume_corrected = self.round_volume(currency, volume)

        # if the min trade size is denoted in ETH and the volume is in ETH, and the volume > min trade size, we're good
        if self.min_trade_size_currency == currency:
            if volume_corrected > self.min_trade_size:
                result = True

        # this would be the trade size in BTC if the trade pair was ETHBTC
        if hasattr(self, 'min_notional'):
            if price * volume_corrected > self.min_notional:
                result = True
            else:
                result = False

        return result, price, volume_corrected

    @abstractmethod
    def get_minimum_deposit_volume(self, currency):
        pass

    # Round the volume to the allowed number of decimal places
    def round_volume(self, currency, volume):

        if not self.decimal_places:
            raise ExchangeError('Cannot determine number of decimal places to round to')

        allowed_decimal_places = self.decimal_places

        logging.debug('Allowed decimal places {} Volume {}'.format(allowed_decimal_places, volume))
        volume_corrected = round_decimal_number(volume, allowed_decimal_places)
        logging.debug('Volume Corrected {} Min Trade Size {}'.format(volume_corrected, self.min_trade_size))
        return volume_corrected

    @abstractmethod
    def get_order(self, order_id):
        pass

    @abstractmethod
    def get_orders(self, order_id):
        pass


class ExchangeError(Exception):
    pass
