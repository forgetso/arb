import json

ORDER_BOOK = {'BTC-ETH':
                          {'success': True, 'result':
                              {
                                  'buy': [{'Rate': '0.09', 'Quantity': '1'}],
                                  'sell': [{'Rate': '0.10', 'Quantity': '1'}]
                              }
                           },
                      'ETH-REP':
                          {'success': True, 'result':
                              {
                                  'buy': [{'Rate': '0.040000', 'Quantity': '1'}],
                                  'sell': [{'Rate': '0.050000', 'Quantity': '1'}]
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
class Exchange1API():
    def __init__(self):
        pass

    def get_orderbook(self, market):
        order_book = ORDER_BOOK

        return order_book[market]
