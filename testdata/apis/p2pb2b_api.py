import datetime as dt

# time just before the order is placed
FAKE_TIME_NOW = dt.datetime(2018, 8, 3, 16, 42, 4, 000000)

class p2pb2bapi:
    def __init__(self, mockdatetime):
        self.datetime = mockdatetime
        pass

    def get_orderbook(self, market):
        order_book = {'success': True, 'result':
            {
                'sell': [{'Rate': '0.08', 'Quantity': '1'}],
                'buy': [{'Rate': '0.0890', 'Quantity': '1'}]
            }}

        return order_book

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
