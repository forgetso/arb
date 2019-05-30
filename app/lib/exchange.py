from abc import ABC, abstractmethod
from app.lib.errors import ErrorTradePairDoesNotExist
from decimal import Decimal, setcontext, Context
from app.lib.common import get_number_of_decimal_places, round_decimal_number
import logging
from app.settings import BASE_CURRENCY


# this abstract class contains all of the methods that an exchange wrap must implement

class exchange(ABC):
    def __init__(self, name, jobqueue_id):
        self.api = None
        self.lowest_ask = None
        self.highest_bid = None
        self.balances = None
        self.balances_time = None
        self.jobqueue_id = jobqueue_id
        self.name = name  # this is set by the inheriting class
        self.min_trade_size_base_currency = None
        super().__init__()

    def set_trade_pair(self, trade_pair, markets):
        try:
            if not self.name:
                raise ValueError('Exchange must have name attribute set')
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

    @abstractmethod
    def order_book(self):
        pass

    @abstractmethod
    def get_currency_pairs(self):
        pass

    @abstractmethod
    def trade(self):
        pass

    @abstractmethod
    def get_order_status(self):
        pass

    @abstractmethod
    def get_order(self):
        pass

    @abstractmethod
    def format_trade(self):
        pass

    @abstractmethod
    def get_balances(self):
        pass

    @abstractmethod
    def get_address(self):
        pass

    @abstractmethod
    def calculate_fees(self):
        pass

    @abstractmethod
    def get_pending_balances(self):
        pass

    def trade_validity(self, price, volume):
        if not self.trade_pair:
            raise ExchangeError('Trade pair must be set')

        if not isinstance(price, Decimal) or not isinstance(volume, Decimal):
            return False, price, volume

        allowed_decimal_places = get_number_of_decimal_places(self.min_trade_size)
        volume_corrected = round_decimal_number(volume, allowed_decimal_places)

        # if price * volume < self.min_trade_size_btc:
        #     volume = self.min_trade_size_btc / price
        result = False
        # finally, check if the volume we're attempting to trade is above the minimum notional trade size
        if volume_corrected > self.min_trade_size:
            result = True

        # this is an extra check to make sure that the trade size is bigger than the smallest trade size allowed in BTC
        if self.quote_currency == BASE_CURRENCY and self.min_trade_size_base_currency is not None:
            if price * volume_corrected > self.min_trade_size_base_currency:
                result = True
            else:
                result = False

        # # TODO work out if non BASE CURRENCY trades are above the BASE_CURRENCY threshold, for example ETH-LTC
        # if self.quote_currency != BASE_CURRENCY:
        #     # raise NotImplementedError('Cannot check if {} trade meets minimum requirements'.format(self.name))
        #     logging.warning(
        #         'Cannot determine if trade meets minimum BTC trade requirements: base {} quote {}'.format(BASE_CURRENCY,
        #                                                                                                   self.quote_currency))
        #     result = True
        return result, price, volume_corrected

    @abstractmethod
    def get_minimum_deposit_volume(self):
        pass


class ExchangeError(Exception):
    pass
