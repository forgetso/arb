from app.wraps.wrap_p2pb2b import p2pb2b, WrapP2PB2BError
from tests.jobs.test_compare import JOBQUEUE_ID
from testdata.markets import MARKETS
import datetime
from decimal import Decimal
from testdata.apis.p2pb2b_api import p2pb2bapi, FAKE_TIME_NOW
from pytest import raises
import time


def setup():
    exchange = p2pb2b(jobqueue_id=JOBQUEUE_ID)
    exchange.set_trade_pair('ETH-BTC', MARKETS)
    return exchange


def test_format_trade():
    exchange = setup()

    raw_trade = {
        "success": True,
        "message": "",
        "result": {
            "offset": 0,
            "limit": 50,
            "records": [
                {
                    "time": 1533310924.000000,
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
    }
    formatted_trade = exchange.format_trade(raw_trade=raw_trade['result'], trade_type='buy', trade_id='blahblah')
    assert isinstance(formatted_trade, dict)
    assert isinstance(formatted_trade['date'], datetime.datetime)
    assert formatted_trade['fees'] == 0
    assert formatted_trade['_id'] == 'blahblah'
    assert formatted_trade['price'] == Decimal("80.22761599")
    assert formatted_trade['volume'] == Decimal("2.12687945")


def test_get_order_status():
    exchange = setup()
    # replace the api with a dummy one
    exchange.api = p2pb2bapi(mockdatetime(FAKE_TIME_NOW))
    # with raises(WrapP2PB2BError):
    #     exchange.get_order_status(order_id='invalid')
    order = exchange.get_order_status(order_id='1237')

    assert order == {}
    time.sleep(0.5)

    order = exchange.get_order_status(order_id='1237')
    assert order == {
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


def test_order_book():
    exchange = setup()
    # replace the api with a dummy one
    exchange.api = p2pb2bapi()
    exchange.trade_pair = 'ETH_BTC'
    exchange.order_book()
    assert exchange.lowest_ask['price'] == Decimal('0.02985')
    assert exchange.highest_bid['price'] == Decimal('0.029842')


# allows us to pretend the order is initially not available and later becomes available
class mockdatetime:
    def __init__(self, time_now):
        self.start = time.time()
        self.time_now = time_now

    def now(self):
        return self.time_now + datetime.timedelta(seconds=(time.time() - self.start))

    def fromtimestamp(self, timestamp):
        return datetime.datetime.fromtimestamp(timestamp)
