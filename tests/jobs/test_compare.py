from app.jobs.compare import determine_arbitrage_viability, find_arbitrage, calculate_profit_and_volume, \
    check_trade_pair, exchange_selection, CompareError, equalise_buy_and_sell_volumes, set_maximum_trade_volume, \
    run_exchange_functions_as_threads, get_downstream_jobs, check_zero_balances
from decimal import Decimal
from pytest import raises
from testdata.wraps import wrap_exchange1, wrap_exchange2
from testdata.markets import MARKETS
import itertools

# TODO globally override the FIAT_ARBITRAGE_MINIMUM as these tests fail when it is set too low


JOBQUEUE_ID = '507f191e810c19729de860ea'


def test_determine_arbitrage_viability():
    # TODO better testing of this function
    exchange1 = wrap_exchange1.exchange1(JOBQUEUE_ID)
    exchange2 = wrap_exchange2.exchange2(JOBQUEUE_ID)
    exchange1.set_trade_pair('ETH-BTC', MARKETS)
    exchange2.set_trade_pair('ETH-BTC', MARKETS)
    exchange1.order_book()
    exchange2.order_book()
    # balances are hard coded into the exchange wrappers
    exchange1.get_balances()
    exchange2.get_balances()
    exchange_permutations = list(itertools.permutations([exchange1, exchange2], 2))
    arbitrages = []
    for perm in exchange_permutations:
        exchange_buy, exchange_sell = perm
        arbitrage = find_arbitrage(exchange_buy, exchange_sell, fiat_rate=100)
        if arbitrage:
            arbitrages.append(arbitrage)
    viable_arbitrages = []
    for arbitrage in arbitrages:
        viable_arbitrages = determine_arbitrage_viability(arbitrage, fiat_rate=100)
    assert len(viable_arbitrages)


def test_replenish_jobs():
    # TODO test replenish function in compare
    pass


def test_find_arbitrage():
    exchange1 = wrap_exchange1.exchange1(JOBQUEUE_ID)
    exchange2 = wrap_exchange2.exchange2(JOBQUEUE_ID)
    exchange1.set_trade_pair('ETH-BTC', MARKETS)
    exchange2.set_trade_pair('ETH-BTC', MARKETS)
    result = find_arbitrage(exchange_x=exchange1, exchange_y=exchange2, fiat_rate=Decimal(100),
                            fiat_arbitrage_minimum=0)
    # at this stage the exchange objects have no ask/bid data attached
    assert result == {}
    exchange1.order_book()
    exchange2.order_book()
    # now we should have order book data in each exchange
    assert exchange1.lowest_ask is not None
    assert exchange2.lowest_ask is not None

    result = find_arbitrage(exchange_x=exchange2, exchange_y=exchange1, fiat_rate=Decimal(100),
                            fiat_arbitrage_minimum=0)
    # an arbitrage should have been found
    assert result != {}
    assert result['buy'].name == 'exchange2'
    assert result['profit'] == Decimal('0.08210')


def test_calculate_profit():
    # Should be able to buy for 1 from exchange_buy
    exchange_buy = wrap_exchange1.exchange1(JOBQUEUE_ID)
    exchange_buy.set_trade_pair('ETH-BTC', MARKETS)
    exchange_buy.lowest_ask = {'price': Decimal('1'), 'volume': Decimal('1')}
    exchange_buy.highest_bid = {'price': Decimal('0.9'), 'volume': Decimal('3')}
    # And sell for 1.1 at exchange_sell
    exchange_sell = wrap_exchange2.exchange2(JOBQUEUE_ID)
    exchange_sell.set_trade_pair('ETH-BTC', MARKETS)
    exchange_sell.lowest_ask = {'price': Decimal('1.2'), 'volume': Decimal('4')}
    exchange_sell.highest_bid = {'price': Decimal('1.1'), 'volume': Decimal('1')}
    # TODO just hard code this

    fiat_rate = Decimal('10')

    _, _, profit = calculate_profit_and_volume(exchange_buy, exchange_sell, fiat_rate)

    # the profit is .1 as we can buy 1 at 1 and sell 1 at 1.1
    # therefore we take the volume from the amount we can sell
    # 1.1 - 1 = 0.1. 0.1 at 10 GBP = 1 GBP profit - fee
    # fee = 1.1 * 0.01 + 1 * 0.01 = 0.021
    # 1 - 0.021 = 0.979
    assert profit == Decimal('0.979')

    fiat_rate = Decimal('100')

    _, _, profit = calculate_profit_and_volume(exchange_buy, exchange_sell, fiat_rate)

    # this just scales up to 10 times the last result
    assert profit == Decimal('9.79')

    fiat_rate = Decimal('1000')

    _, _, profit = calculate_profit_and_volume(exchange_buy, exchange_sell, fiat_rate)

    # max size of trade we will so is FIAT_REPLENISH_AMOUNT, set to 100 GBP in settings
    # therefore buying 1 for 1000 GBP is not possible. We will again buy 100 GBPs worth
    # this result must be the same as the previous one
    assert profit == Decimal('9.79')

    exchange_buy.fee = Decimal('0.01')
    exchange_sell.fee = Decimal('0.01')

    _, _, profit = calculate_profit_and_volume(exchange_buy, exchange_sell, fiat_rate)
    fee = (Decimal('0.01') * Decimal('1') * Decimal('1') + Decimal('0.01') * Decimal('1.1') * Decimal('1'))
    # we can only buy a tenth of the volume available due to the FIAT_REPLENISH_AMOUNT limit
    # therefore profit should just be the same as the last result minus the fees
    profit_test = (Decimal('0.1') - fee) / 10 * Decimal('1000')
    assert profit == profit_test

    # the lowest_ask fields are empty resulting in an error in the function
    exchange_buy.lowest_ask = {}
    with raises(CompareError):
        calculate_profit_and_volume(exchange_buy, exchange_sell, fiat_rate)

    # the following will result in an invalid trade and the profit is assumed to be 0
    exchange_buy.lowest_ask = {'price': 'blahblah', 'volume': 'blahlah'}
    with raises(TypeError):
        calculate_profit_and_volume(exchange_buy, exchange_sell, fiat_rate)


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


def test_equalise_buy_and_sell_volumes():
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
    # Volume should come out as 1 as we can only sell 1 at price 1.1
    exchange_permutation = equalise_buy_and_sell_volumes(exchange_buy, exchange_sell)
    assert exchange_permutation[0].lowest_ask['volume'] == Decimal('1')
    assert exchange_permutation[1].highest_bid['volume'] == Decimal('1')


def test_set_maximum_trade_volume():
    # this will come out at 200 GBP but our max is 100 GBP
    volume = 100
    price = 1
    fiat_rate = 2
    volume = set_maximum_trade_volume(volume, price, fiat_rate)
    assert volume == 50

    # this will come out at 50 GBP so volume does not need to be reduced
    volume = 100
    fiat_rate = 0.5
    volume = set_maximum_trade_volume(volume, price, fiat_rate)
    assert volume == 100


def test_run_exchange_functions_as_threads():
    exchange_buy = wrap_exchange1.exchange1(JOBQUEUE_ID)
    exchange_sell = wrap_exchange2.exchange2(JOBQUEUE_ID)
    exchange_buy.set_trade_pair('ETH-BTC', markets=MARKETS)
    exchange_sell.set_trade_pair('ETH-BTC', markets=MARKETS)
    exchanges = [exchange_buy, exchange_sell]
    run_exchange_functions_as_threads(exchanges, 'order_book')
    assert exchange_buy.lowest_ask is not None
    assert exchange_sell.lowest_ask is not None


def test_get_downstream_jobs():
    fiat_rate = 1
    exchange1 = wrap_exchange1.exchange1(JOBQUEUE_ID)
    exchange2 = wrap_exchange2.exchange2(JOBQUEUE_ID)
    exchange1.set_trade_pair('ETH-BTC', MARKETS)
    exchange2.set_trade_pair('ETH-BTC', MARKETS)
    exchange1.order_book()
    exchange2.order_book()
    exchange1.get_balances()
    exchange2.get_balances()
    arbitrage = find_arbitrage(exchange2, exchange1, fiat_rate, fiat_arbitrage_minimum=0)
    replenish_jobs, viable_arbitrages = get_downstream_jobs([arbitrage], fiat_rate)
    assert len(viable_arbitrages) == 2


def test_check_zero_balances():
    exchange1 = wrap_exchange1.exchange1(JOBQUEUE_ID)
    exchange2 = wrap_exchange2.exchange2(JOBQUEUE_ID)
    exchange1.set_trade_pair('ETH-ADX', MARKETS)
    exchange2.set_trade_pair('ETH-ADX', MARKETS)
    exchange1.get_balances()
    exchange2.get_balances()
    arbitrage = {'buy': exchange1, 'sell': exchange2}
    replenish_jobs = check_zero_balances(arbitrage)
    assert replenish_jobs == [{'job_type': 'REPLENISH', 'job_args': {'exchange': 'exchange1', 'currency': 'ADX'}},
                              {'job_type': 'REPLENISH', 'job_args': {'exchange': 'exchange1', 'currency': 'ETH'}},
                              {'job_type': 'REPLENISH', 'job_args': {'exchange': 'exchange2', 'currency': 'ADX'}}]
