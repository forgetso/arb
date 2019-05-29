from abc import ABC, abstractmethod
from app.lib.errors import ErrorTradePairDoesNotExist
from decimal import Decimal, setcontext, Context


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

    @abstractmethod
    def trade_validity(self):
        pass

    @abstractmethod
    def get_minimum_deposit_volume(self):
        pass
