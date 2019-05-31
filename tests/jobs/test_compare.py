from app.jobs.compare import determine_arbitrage_viability, find_arbitrage, calculate_profit, check_trade_pair, \
    exchange_selection, CompareError
from decimal import Decimal
from pytest import raises, fixture
from app.lib import exchange
from testdata.wraps import wrap_exchange1, wrap_exchange2

# this would usually be loaded from a json file
MARKETS = {'exchange1':
    {"ETH-BTC": {
        "name": "ETH-BTC",
        "trading_code": "BTC-ETH",
        "base_currency": "ETH",
        "quote_currency": "BTC",
        "min_trade_size": 0.00740642,
        "min_trade_size_currency": "ETH",
        "fee": 0.001
    }},
    'exchange2':
        {"ETH-BTC": {
            "name": "ETH-BTC",
            "trading_code": "ETHBTC",
            "base_currency": "ETH",
            "quote_currency": "BTC",
            "decimal_places": 3,
            "min_trade_size": 0.001,
            "min_trade_size_currency": "ETH",
            "min_notional": 0.001,
            "taker_fee": 0.001,
            "maker_fee": 0.001,
            "fee": 0.001
        }},
    # this exchange will be ignored as it doesn't exist in our allowed list of exchanges
    'exchange3':
        {"ETH-BTC": {
            "name": "ETH-BTC",
            "trading_code": "ETHBTC",
            "base_currency": "ETH",
            "quote_currency": "BTC",
            "decimal_places": 3,
            "min_trade_size": 0.001,
            "min_trade_size_currency": "ETH",
            "min_notional": 0.001,
            "taker_fee": 0.001,
            "maker_fee": 0.001,
            "fee": 0.001
        }}
}

JOBQUEUE_ID = '507f191e810c19729de860ea'


def test_determine_arbitrage_viability():
    exchange1 = wrap_exchange1.exchange1(JOBQUEUE_ID)
    exchange2 = wrap_exchange1.exchange1(JOBQUEUE_ID)
    exchange1.set_trade_pair('ETH-BTC', MARKETS)
    exchange2.set_trade_pair('ETH-BTC', MARKETS)
    exchange1.order_book()
    exchange2.order_book()
    exchange1.get_balances()
    exchange2.get_balances()
    arbitrages = [find_arbitrage(exchange1, exchange2, fiat_rate=100)]
    viable_arbitrages, replenish_jobs, profit_audit = determine_arbitrage_viability(arbitrages)
    assert len(viable_arbitrages)
    assert not len(replenish_jobs)


def test_find_arbitrage():
    exchange1 = wrap_exchange1.exchange1(JOBQUEUE_ID)
    exchange2 = wrap_exchange2.exchange2(JOBQUEUE_ID)
    exchange1.set_trade_pair('ETH-BTC', MARKETS)
    exchange2.set_trade_pair('ETH-BTC', MARKETS)
    result = find_arbitrage(exchange_x=exchange1, exchange_y=exchange2, fiat_rate=Decimal(100))
    # at this stage the exchange objects have no ask/bid data attached
    assert result == {}
    exchange1.order_book()
    exchange2.order_book()
    # now we should have order book data in each exchange
    assert exchange1.lowest_ask is not None
    assert exchange2.lowest_ask is not None
    result = find_arbitrage(exchange_x=exchange1, exchange_y=exchange2, fiat_rate=Decimal(100))
    # an arbitrage should have been found
    assert result != {}
    assert result['buy'].name == 'exchange1'
    assert result['profit'] == Decimal('0.983')


def test_calculate_profit():
    # Should be able to buy for 1 from exchange_buy
    exchange_buy = wrap_exchange1.exchange1(JOBQUEUE_ID)
    exchange_buy.set_trade_pair('ETH-BTC', MARKETS)
    exchange_buy.lowest_ask = {'price': Decimal('1'), 'volume': Decimal('50')}
    exchange_buy.highest_bid = {'price': Decimal('0.9'), 'volume': Decimal('3')}
    # And sell for 1.1 at exchange_sell
    exchange_sell = wrap_exchange2.exchange2(JOBQUEUE_ID)
    exchange_sell.set_trade_pair('ETH-BTC', MARKETS)
    exchange_sell.lowest_ask = {'price': Decimal('1.2'), 'volume': Decimal('4')}
    exchange_sell.highest_bid = {'price': Decimal('1.1'), 'volume': Decimal('1')}

    fiat_rate = Decimal('10')

    profit = calculate_profit(exchange_buy, exchange_sell, fiat_rate)

    # the profit is 1 as we can buy 50 at 1 but sell only 1 at 1.1
    # therefore we take the volume from the amount we can sell
    # 1.1 - 1 = 0.1. 0.1 at 10 GBP = 1 GBP profit - fee
    # fee = 1.1 * 0.01 + 1 * 0.01 = 0.021
    # 1 - 0.021 = 0.979
    assert profit == Decimal('0.979')

    fiat_rate = Decimal('100')

    profit = calculate_profit(exchange_buy, exchange_sell, fiat_rate)

    # this just scales up to 10 times the last result
    assert profit == Decimal('9.79')

    fiat_rate = Decimal('1000')

    profit = calculate_profit(exchange_buy, exchange_sell, fiat_rate)

    # max size of trade we will so is FIAT_REPLENISH_AMOUNT, set to 100 GBP in settings
    # therefore buying 1 for 1000 GBP is not possible. We will again buy 100 GBPs worth
    # this result must be the same as the previous one
    assert profit == Decimal('9.79')

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
    with raises(TypeError):
        calculate_profit(exchange_buy, exchange_sell, fiat_rate)


def test_check_trade_pair():
    assert check_trade_pair(['ETH', 'BTC'])
    with raises(ValueError):
        check_trade_pair(['ETH'])
    with raises(TypeError):
        check_trade_pair([Decimal('1212'), True])


def test_exchange_selection():
    jobqueue_id = JOBQUEUE_ID
    cur_x = 'ETH'
    cur_y = 'BTC'
    exchange_list = ['exchange1', 'exchange2']
    exchanges_selected = exchange_selection(cur_x, cur_y, MARKETS, exchange_list, jobqueue_id,
                                            directory='testdata.wraps.wrap')
    assert [x.name for x in exchanges_selected] == ['exchange1', 'exchange2']

    with raises(ImportError):
        exchange_selection(cur_x, cur_y, MARKETS, exchange_list, jobqueue_id, directory='blah.blah')
