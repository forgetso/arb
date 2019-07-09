import datetime as dt

# time just before the order is placed
FAKE_TIME_NOW = dt.datetime(2018, 8, 3, 16, 42, 4, 000000)


class p2pb2bapi:
    def __init__(self, mockdatetime=None):
        if mockdatetime:
            self.datetime = mockdatetime
        else:
            self.datetime = dt.datetime
        pass

    def getBook(self, market, side, limit):

        order_book = {'buy': {"success": True,
                              "message": "",
                              "result":
                                  {'offset': 0, 'limit': 1, 'total': 362, 'orders': [
                                      {'id': 14835298, 'left': '1.375', 'market': 'ETH_BTC', 'amount': '2.909',
                                       'type': 'limit',
                                       'price': '0.029842', 'timestamp': 1556176474.980993, 'side': 'buy',
                                       'dealFee': '0',
                                       'takerFee': '0',
                                       'makerFee': '0', 'dealStock': '1.534', 'dealMoney': '0.045777628'}]}},
                      'sell': {"success": True,
                               "message": "",
                               "result":
                                   {'offset': 0, 'limit': 1, 'total': 408, 'orders': [
                                       {'id': 14855016, 'left': '60.222', 'market': 'ETH_BTC', 'amount': '60.222',
                                        'type': 'limit',
                                        'price': '0.02985', 'timestamp': 1556192089.28709, 'side': 'sell',
                                        'dealFee': '0',
                                        'takerFee': '0.002',
                                        'makerFee': '0.002', 'dealStock': '0', 'dealMoney': '0'}]}}}

        return order_book[side]

    def getOrder(self, order_id):
        orders = {
            '1237': {
                "success": True,
                "message": "",
                "result": {
                    "offset": 0,
                    "limit": 50,
                    "records": [
                        {
                            "time": 1533310924.500000,
                            "fee": "0",
                            "price": "80.22761599",
                            "amount": "2.12687945",
                            "id": 548,
                            "dealOrderId": 1237,
                            "role": 1,
                            "deal": "170.6344677716224055"
                        }
                    ]
                }
            },
            'invalid': {'success': False, 'message': {'orderId': ['The order id must be an integer.']}, 'result': []},
            '123456': {'success': True, 'message': '', 'result': {'offset': 0, 'limit': 50, 'records': []}}
        }
        if order_id in orders:
            order_time = orders[order_id]['result']['records'][0]['time']
            order_time = self.datetime.fromtimestamp(order_time)
            now = self.datetime.now()
            print(order_time)
            print(now)
            if order_time < now:
                print('order is available')
                result = orders[order_id]
            else:
                result = orders[order_id]
                result['result']['records'] = []
                print('order is not available')
        else:
            result = {'success': False}
        return result
