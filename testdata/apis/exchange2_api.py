import json
from decimal import Decimal


class Exchange2API():
    def __init__(self):
        pass

    def get_orderbook(self, market):
        order_book = {'ETHBTC':
                          {'success': True, 'result':
                              {
                                  'buy': [{'Rate': '0.08', 'Quantity': '1'}],
                                  'sell': [{'Rate': '0.0890', 'Quantity': '1'}]
                              }
                           },
                      'REP-BTC':
                          {'success': True, 'result':
                              {
                                  'buy': [{'Rate': '0.0020000', 'Quantity': '1'}],
                                  'sell': [{'Rate': '0.0030000', 'Quantity': '1'}]
                              }
                           },
                      }

        return order_book[market]
