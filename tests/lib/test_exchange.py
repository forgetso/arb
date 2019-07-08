from tests.jobs.test_compare import JOBQUEUE_ID
from testdata.wraps.wrap_exchange1 import exchange1
from pytest import raises
from decimal import Decimal


def test_trade_validity():
    e = exchange1(jobqueue_id=JOBQUEUE_ID)
    e.min_notional = Decimal('2')
    e.trade_pair = 'ETH-BTC'
    e.decimal_places = 4
    e.min_trade_size = Decimal('0.005')
    e.min_trade_size_currency = 'ETH'

    with raises(TypeError):
        e.trade_validity('ETH', 0.24567, 2)

    # min notional is 2 but notional value is 0.24567 * 2 = 0.49134 so this trade should be invalid
    result, _, _ = e.trade_validity('ETH', Decimal('0.24567'), Decimal('2'))
    assert result is False

    # this trade should be valid
    result, _, _ = e.trade_validity('ETH', Decimal('0.24567'), Decimal('20'))
    assert result is True

    e.min_trade_size = Decimal('0.005')  # size of trade in ETH
    e.min_notional = Decimal('0.0002')  # size of trade in BTC

    # following is above the min notional but below min trade size. Should still result in False
    result, _, _ = e.trade_validity('ETH', price=Decimal('0.2'), volume=Decimal('0.001'))
    assert result is False

    e.min_notional = Decimal('0.0003')  # size of trade in BTC

    # following is below min notional and below min trade size. Should result in False
    result, _, _ = e.trade_validity('ETH', price=Decimal('0.2'), volume=Decimal('0.001'))
    assert result is False

    # following is above min notional and equal to min trade size in ETH
    result, _, _ = e.trade_validity('ETH', price=Decimal('0.2'), volume=Decimal('0.005'))
    assert result is True

    # following is below min trade size in BTC
    e.min_trade_size_currency = 'BTC'
    e.min_trade_size = Decimal('0.0005')
    result, _, _ = e.trade_validity('ETH', price=Decimal('0.02'), volume=Decimal('0.001'))
    assert result is False
