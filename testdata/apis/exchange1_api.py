import json


class Exchange1API():
    def __init__(self):
        pass

    def get_orderbook(self, market):
        order_book = {'success': True, 'result':
            {
                'sell': [{'Rate': '0.08', 'Quantity': '1'}],
                'buy': [{'Rate': '0.0890', 'Quantity': '1'}]
            }}

        return order_book
