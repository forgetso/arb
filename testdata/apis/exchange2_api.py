import json
from decimal import Decimal


class Exchange2API():
    def __init__(self):
        pass

    def get_orderbook(self, market):
        order_book = {'success': True, 'result':
            {
                'sell': [{'Rate': '0.089', 'Quantity': '1'}],
                'buy': [{'Rate': '0.09', 'Quantity': '1'}]
            }}
        return order_book
