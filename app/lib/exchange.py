from abc import ABC, abstractmethod



# this abstract class contains all of the methods that an exchange wrap must implement

class exchange(ABC):
    def __init__(self, jobqueue_id):
        self.api = None
        self.lowest_ask = None
        self.highest_bid = None
        self.balances = None
        self.balances_time = None
        self.jobqueue_id = jobqueue_id
        super().__init__()

    @abstractmethod
    def set_trade_pair(self, trade_pair, markets):
        pass

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
