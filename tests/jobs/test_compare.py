from app.jobs.compare import calculate_profit
from decimal import Decimal


def test_calculate_profit():
    # Should be able to buy for 1 from exchange_buy
    exchange_buy = exchange()
    exchange_buy.lowest_ask = {'price': Decimal('1'), 'volume': Decimal('50')}
    exchange_buy.highest_bid = {'price': Decimal('0.9'), 'volume': Decimal('3')}
    # And sell for 1.1 at exchange_sell
    exchange_sell = exchange()
    exchange_sell.lowest_ask = {'price': Decimal('1'), 'volume': Decimal('4')}
    exchange_sell.highest_bid = {'price': Decimal('1.1'), 'volume': Decimal('1')}
    fiat_rate = Decimal('10')
    profit = calculate_profit(exchange_buy, exchange_sell, fiat_rate)
    assert profit == Decimal('1')


class exchange():

    def __init__(self):
        self.lowest_ask = {}
        self.highest_bid = {}
        self.fee = Decimal(0)

    def trade_validity(self, price, volume):
        return True, price, volume
