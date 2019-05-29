from app.jobs.compare import calculate_profit, CompareError, check_trade_pair, exchange_selection
from decimal import Decimal
from pytest import raises, fixture


def test_calculate_profit():
    # Should be able to buy for 1 from exchange_buy
    exchange_buy = exchange()
    exchange_buy.lowest_ask = {'price': Decimal('1'), 'volume': Decimal('50')}
    exchange_buy.highest_bid = {'price': Decimal('0.9'), 'volume': Decimal('3')}
    # And sell for 1.1 at exchange_sell
    exchange_sell = exchange()
    exchange_sell.lowest_ask = {'price': Decimal('1.2'), 'volume': Decimal('4')}
    exchange_sell.highest_bid = {'price': Decimal('1.1'), 'volume': Decimal('1')}

    fiat_rate = Decimal('10')

    profit = calculate_profit(exchange_buy, exchange_sell, fiat_rate)

    # the profit is 1 as we can buy 50 at 1 but sell only 1 at 1.1
    # therefore we take the volume from the amount we can sell
    # 1.1 - 1 = 0.1. 0.1 at 10 GBP = 1 GBP profit
    assert profit == Decimal('1.0')

    fiat_rate = Decimal('100')

    profit = calculate_profit(exchange_buy, exchange_sell, fiat_rate)

    # this just scales up to 10 times the last result
    assert profit == Decimal('10')

    fiat_rate = Decimal('1000')

    profit = calculate_profit(exchange_buy, exchange_sell, fiat_rate)

    # max size of trade we will so is FIAT_REPLENISH_AMOUNT, set to 100 GBP in settings
    # therefore buying 1 for 1000 GBP is not possible. We will again buy 100 GBPs worth
    # this result must be the same as the previous one
    assert profit == Decimal('10')

    exchange_buy.fee = Decimal('0.01')
    exchange_sell.fee = Decimal('0.01')

    profit = calculate_profit(exchange_buy, exchange_sell, fiat_rate)
    fee = (Decimal('0.01') * Decimal('1') * Decimal('1') + Decimal('0.01') * Decimal('1.1') * Decimal('1'))
    # we can only buy a tenth of the volume available due to the FIAT_REPLENISH_AMOUNT limit
    # therefore profit should just be the same as the last result minus the fees
    profit_test = (Decimal('0.1') - fee) / 10 * Decimal('1000')
    assert profit == profit_test

    # the lowest_ask fields are empty resulting in an error in the function
    exchange_buy.lowest_ask = {}
    with raises(CompareError):
        calculate_profit(exchange_buy, exchange_sell, fiat_rate)

    # the following will result in an invalid trade and the profit is assumed to be 0
    exchange_buy.lowest_ask = {'price': 'blahblah', 'volume': 'blahlah'}
    profit = calculate_profit(exchange_buy, exchange_sell, fiat_rate)
    assert profit == Decimal('0')


def test_check_trade_pair():
    assert check_trade_pair(['ETH', 'BTC'])
    with raises(ValueError):
        check_trade_pair(['ETH'])
    with raises(TypeError):
        check_trade_pair([Decimal('1212'), True])


def test_exchange_selection():
    markets = {'exchange1':
        {"ETH-BTC": {
            "name": "ETH-BTC",
            "trading_code": "BTC-ETH",
            "base_currency": "ETH",
            "quote_currency": "BTC",
            "min_trade_size": 0.00740642,
            "fee": 0.0025
        }},
        'exchange2':
            {"ETH-BTC": {
                "name": "ETH-BTC",
                "trading_code": "ETHBTC",
                "base_currency": "ETH",
                "quote_currency": "BTC",
                "decimal_places": 3,
                "min_trade_size": 0.001,
                "min_notional": 0.001,
                "taker_fee": 0.001,
                "maker_fee": 0.001,
                "fee": 0.001
            }},
        # this exchange will be ignored as it doesn't exist in our allowed list of EXCHANGES
        'exchange3':
            {"ETH-BTC": {
                "name": "ETH-BTC",
                "trading_code": "ETHBTC",
                "base_currency": "ETH",
                "quote_currency": "BTC",
                "decimal_places": 3,
                "min_trade_size": 0.001,
                "min_notional": 0.001,
                "taker_fee": 0.001,
                "maker_fee": 0.001,
                "fee": 0.001
            }}
    }
    jobqueue_id = '507f1f77bcf86cd799439011'
    cur_x = 'ETH'
    cur_y = 'BTC'
    exchange_list = ['exchange1', 'exchange2']
    exchanges_selected = exchange_selection(cur_x, cur_y, markets, exchange_list, jobqueue_id,
                                            directory='testdata.wraps.wrap')
    assert [x.name for x in exchanges_selected] == ['exchange1', 'exchange2']

    # TODO extract the generic parts of all exchanges and make a generic base class for all exchanges to inherit properties from


class exchange():

    def __init__(self):
        self.lowest_ask = {}
        self.highest_bid = {}
        self.fee = Decimal(0)

    def trade_validity(self, price, volume):
        # this function differs per exchange and involves rounding volumes and prices to the required precisions
        # this is a very simple test implementation to allow for valid and invalid trades
        valid = False
        if isinstance(price, Decimal) and isinstance(volume, Decimal):
            valid = True
        return valid, price, volume