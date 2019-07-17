from app.lib.exchange import exchange, ExchangeError
from testdata.apis.exchange1_api import Exchange1API
from decimal import Decimal


class exchange1(exchange):

    def __init__(self, jobqueue_id):
        self.name = 'exchange1'
        exchange.__init__(self, name=self.name, jobqueue_id=jobqueue_id)
        self.api = Exchange1API()
        return

    def order_book(self):
        order_book_dict = self.api.get_orderbook(market=self.trade_pair)
        if not order_book_dict.get('success'):
            raise (ExchangeError(order_book_dict.get('message')))

        self.asks = [{'price': Decimal(x['Rate']), 'volume': Decimal(x['Quantity'])} for x in
                     order_book_dict.get('result', {}).get('asks', [])]
        if len(self.asks):
            self.lowest_ask = self.asks[0]
        self.bids = [{'price': Decimal(x['Rate']), 'volume': Decimal(x['Quantity'])} for x in
                     order_book_dict.get('result', {}).get('bids', [])]
        if len(self.bids):
            self.highest_bid = self.bids[0]
        return order_book_dict

    def get_currency_pairs(self):
        return

    def trade(self):
        return

    def get_order_status(self):
        return

    def get_order(self, order_id):
        return

    def format_trade(self):
        return

    def get_balances(self):
        self.balances = {'ETH': Decimal('0'), 'BTC': Decimal('0.005')}
        return

    def get_address(self):
        return

    def calculate_fees(self):
        return

    def get_pending_balances(self):
        return

    def get_minimum_deposit_volume(self):
        return

    def get_orders(self, order_id):
        return
