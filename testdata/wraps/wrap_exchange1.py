from app.lib.exchange import exchange
from decimal import Decimal, setcontext, Context

class exchange1(exchange):

    def __init__(self, jobqueue_id):
        self.name = 'exchange1'
        exchange.__init__(self, jobqueue_id=jobqueue_id)
        return

    def set_trade_pair(self, trade_pair, markets):
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
        return

    def order_book(self):
        return

    def get_currency_pairs(self):
        return

    def trade(self):
        return

    def get_order_status(self):
        return

    def get_order(self):
        return

    def format_trade(self):
        return

    def get_balances(self):
        return

    def get_address(self):
        return

    def calculate_fees(self):
        return

    def get_pending_balances(self):
        return

    def trade_validity(self):
        return

    def get_minimum_deposit_volume(self):
        return
