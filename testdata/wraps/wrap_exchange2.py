from app.lib.exchange import exchange


class exchange2(exchange):

    def __init__(self, jobqueue_id):
        self.name = 'exchange2'
        exchange.__init__(self, name=self.name, jobqueue_id=jobqueue_id)
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

    def get_minimum_deposit_volume(self):
        return
