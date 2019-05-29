from app.lib.common import get_number_of_decimal_places, get_replenish_quantity, CommonError, \
    get_number_of_places_before_point, round_decimal_number, decimal_as_string
from app.settings import FIAT_REPLENISH_AMOUNT
from decimal import Decimal
from pytest import raises


def test_get_number_of_decimal_places():
    assert get_number_of_decimal_places(Decimal('0.001')) == 3
    assert get_number_of_decimal_places(Decimal('0.00000000000001')) == 14
    assert get_number_of_decimal_places(Decimal('0.000000000000010')) == 15
    assert get_number_of_decimal_places(Decimal('1.12')) == 2
    assert get_number_of_decimal_places(Decimal('0.12')) == 2
    assert get_number_of_decimal_places(0.001) == 3


def test_get_replenish_quantity():
    fiat_rate = 1
    assert get_replenish_quantity(fiat_rate) == FIAT_REPLENISH_AMOUNT * fiat_rate
    with raises(CommonError):
        get_replenish_quantity('a')
    assert get_replenish_quantity(Decimal(fiat_rate)) == FIAT_REPLENISH_AMOUNT * fiat_rate


def test_get_number_of_places_before_point():
    assert get_number_of_places_before_point(1.01) == 1
    assert get_number_of_places_before_point(11.1) == 2
    assert get_number_of_places_before_point(Decimal('100.0'))
    with raises(CommonError):
        get_number_of_places_before_point('11.1')


def test_round_decimal_number():
    assert round_decimal_number(1.0, 1) == 1.0
    assert round_decimal_number(100.0101010101, 0) == 100
    assert round_decimal_number(100.000, 0) == 100
    assert round_decimal_number(Decimal('100.111111111111111111111111111111'), 2) == Decimal('100.11')
    assert round_decimal_number(3, 0) == 3


def test_decimal_as_string():
    assert decimal_as_string(4.5) == '4.5'
    assert decimal_as_string(0.1) == '0.1'
    assert decimal_as_string(Decimal('1.11111')) == '1.11111'
    assert decimal_as_string(1) == '1'
    with raises(CommonError):
        decimal_as_string('a')
    with raises(CommonError):
        decimal_as_string(float)

#TODO coingecko API tests