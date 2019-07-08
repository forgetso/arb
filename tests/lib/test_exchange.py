from tests.jobs.test_compare import JOBQUEUE_ID
from testdata.wraps.wrap_exchange1 import exchange1
from pytest import raises
from decimal import Decimal


def test_trade_validity():
    e = exchange1(jobqueue_id=JOBQUEUE_ID)
    e.min_notional = 2
    e.trade_pair = 'ETH-BTC'
    e.decimal_places = 3
    e.min_trade_size = 0.005

    with raises(TypeError):
        e.trade_validity('ETH', 0.24567, 2)

    # min notional is 2 but notional value is 0.24567 * 2 = 0.49134 so this trade should be invalid
    result, _, _ = e.trade_validity('ETH', Decimal('0.24567'), Decimal('2'))
    assert result is False

    # this trade should be valid
    result, _, _ = e.trade_validity('ETH', Decimal('0.24567'), Decimal('20'))
    assert result is True
