from app.lib.exchange import exchange, ExchangeError
from testdata.apis.exchange2_api import Exchange2API
from decimal import Decimal


class exchange2(exchange):

    def __init__(self, jobqueue_id):
        self.name = 'exchange2'
        exchange.__init__(self, name=self.name, jobqueue_id=jobqueue_id)
        self.api = Exchange2API()
        return

    def order_book(self):
        order_book_dict = self.api.get_orderbook(market=self.trade_pair)
        if not order_book_dict.get('success'):
            raise (ExchangeError(order_book_dict.get('message')))
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
        self.balances = {'ETH': Decimal('1'), 'BTC': Decimal('0.01')}
        return

    def get_address(self):
        return

    def calculate_fees(self):
        return

    def get_pending_balances(self):
        return

    def get_minimum_deposit_volume(self):
        return
