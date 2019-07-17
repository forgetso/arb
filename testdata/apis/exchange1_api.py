ORDER_BOOK = {'BTC-ETH':
                  {'success': True, 'result':
                      {
                          'bids': [{'Rate': '0.09', 'Quantity': '1'},
                                   {'Rate': '0.088', 'Quantity': '0.007'},
                                   {'Rate': '0.087', 'Quantity': '0.998'}
                                   ],
                          'asks': [{'Rate': '0.10', 'Quantity': '2'},
                                   {'Rate': '0.11', 'Quantity': '1'}]
                      },

                   },
              'ETH-REP':
                  {'success': True, 'result':
                      {
                          'bids': [{'Rate': '0.040000', 'Quantity': '1'}],
                          'asks': [{'Rate': '0.050000', 'Quantity': '1'}]
                      }
                   },
              'REP-BTC':
                  {'success': True, 'result':
                      {
                          'bids': [{'Rate': '0.0020000', 'Quantity': '1'}],
                          'asks': [{'Rate': '0.0030000', 'Quantity': '1'}]
                      }
                   },
              }


class Exchange1API():
    def __init__(self):
        pass

    def get_orderbook(self, market):
        order_book = ORDER_BOOK

        return order_book[market]
