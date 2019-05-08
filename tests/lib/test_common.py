from app.lib.common import get_number_of_decimal_places, get_replenish_quantity, CommonError
from app.settings import FIAT_REPLENISH_AMOUNT
from decimal import Decimal
from pytest import raises


def test_get_number_of_decimal_places():
    assert get_number_of_decimal_places(Decimal('0.001')) == 3
    assert get_number_of_decimal_places(Decimal('0.00000000000001')) == 14
    assert get_number_of_decimal_places(Decimal('0.000000000000010')) == 15
    assert get_number_of_decimal_places(Decimal('1.12')) == 2
    assert get_number_of_decimal_places(Decimal('0.12')) == 2
    with raises(TypeError):
        get_number_of_decimal_places(0.001)


def test_get_replenish_quantity():
    fiat_rate = 1
    assert get_replenish_quantity(fiat_rate) == FIAT_REPLENISH_AMOUNT * fiat_rate
    with raises(CommonError):
        get_replenish_quantity('a')
    assert get_replenish_quantity(Decimal(fiat_rate)) == FIAT_REPLENISH_AMOUNT * fiat_rate
