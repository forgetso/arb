from app.wraps.wrap_binance import binance
from app.lib.setup import load_currency_pairs
from app.jobs.compare import run_exchange_functions_as_threads, get_fiat_rate
from decimal import Decimal
import logging
import pprint
import time
import math
from app.lib.bellmanford import bellman_ford
from app.tools.all_combinations import process as all_trading_combinations
import random
from app.lib.setup import choose_random_exchanges, dynamically_import_exchange

def match_order_book(exchange, to_sell, buy_type):
    depth = 0
    to_buy = 0
    try:
        # if pair is ETH-BTC, volume is in ETH, price is in BTC
        # BTC volume is volume * price
        # if buy type is asks, we are selling BTC (to_sell) for ETH (to_buy)
        # if buy type is bids, we are selling ETH (to_sell) for BTC (to_buy)
        bids = exchange.bids
        asks = exchange.asks
        logging.debug(exchange.name)
        assert bids[0]['price'] < asks[0]['price']
        while to_sell >= 0:
            if buy_type == 'asks':
                # each one of these buys and sells would need to be stored and then executed individually
                to_sell -= asks[depth]['volume']
                to_buy += asks[depth]['volume'] * bids[depth]['price']
            elif buy_type == 'bids':
                to_buy += bids[depth]['volume']
                to_sell -= bids[depth]['volume'] * asks[depth]['price']
            depth += 1

        if to_sell < 0:
            if buy_type == 'asks':
                # Trying to buy too much ETH. Take some off, equivalent to how much we went past zero
                # print('buying too much {} {}'.format(to_buy, to_sell))
                to_buy -= -to_sell * asks[depth]['price']
                # print('buying now')
                # print(to_buy)

            elif buy_type == 'bids':
                # Trying to buy too much BTC. Take some off, equivalent to how much we went past zero
                logging.debug('buying too much {} {}'.format(to_buy, to_sell))
                to_buy -= -to_sell / bids[depth]['price']
                logging.debug('buying now')
                logging.debug(to_buy)
    except IndexError:
        print('Not enough {} to complete trade. {} {}'.format(buy_type, len(getattr(exchange, buy_type)), buy_type))

    return to_buy


def construct_rate_graph(currencies, exchanges):
    graph = {}
    for currency in currencies:
        for exchange in exchanges:
            graph.setdefault(currency, {})
            # Example base_currency is REP
            # we are on the REP row
            # how much of quote currency do we get for 1 REP?
            # this is simply the highest bid for REP on the exchange
            if currency == exchange.base_currency:
                graph[currency][exchange.quote_currency] = -math.log(exchange.highest_bid['price'])
            # Example quote_currency is in BTC
            # so we are on the BTC row
            # then set the number of base_currency we will get for 1 BTC
            # this is determined by dividing 1 by the lowest ask price in BTC (e.g. 1/0.005 = 200 REP for 1 BTC)
            if currency == exchange.quote_currency:
                graph[currency][exchange.base_currency] = -math.log(Decimal('1') / exchange.lowest_ask['price'])

    logging.debug('Currencies are {} '.format(currencies))

    pprint.pprint(graph)

    return graph


def process():
    exchanges = []
    # trade pairs are BUY-SELL
    # get all trade pairs that exist on every exchange
    pairs = list(all_trading_combinations())

    # choose 3 at random (fix to avoid clashes)
    pairs_index = [random.randint(0, len(pairs)), random.randint(0, len(pairs)), random.randint(0, len(pairs))]
    # pairs = [pairs[i] for i in pairs_index]

    # just choose 3
    pairs = ['ETC-BTC', 'ETC-ETH', 'ETH-BTC']
    print('chosen pairs {}'.format(pairs))

    random_exchanges = choose_random_exchanges(number=len(pairs))
    for exchange in random_exchanges:
        exchanges.append(dynamically_import_exchange(exchange)('xxx'))

    markets = load_currency_pairs()

    currencies = []

    for count, pair in enumerate(pairs):
        exchanges[count].set_trade_pair(pair, markets)
        currencies.append(exchanges[count].base_currency)
        currencies.append(exchanges[count].quote_currency)

    # this is needed for bellman ford algorithm
    currencies = sorted(list(set(currencies)))

    # generate the order books for each trade pair
    run_exchange_functions_as_threads(exchanges, 'order_book')

    # start the timer
    start_time = time.time()

    # initially we want to look at the first order in the order book
    initial_depth = 1

    # store all the buy volumes in a list
    buys = list()

    # first buy volume is just whatever the volume of the lowest ask is (up to initial depth)
    buys.append(sum([x['volume'] for x in exchanges[0].asks[0:initial_depth]]))

    initial_cost = sum([x['volume'] * x['price'] for x in exchanges[0].asks[0:initial_depth]])
    logging.debug('buying {} {} for initial {} {}'.format(buys[0], exchanges[0].base_currency, initial_cost,
                                                          exchanges[0].quote_currency))

    fiat_rate = get_fiat_rate(exchanges[0].quote_currency)
    initial_cost_fiat = fiat_rate * initial_cost

    # if we're going BTC -> ETC -> ETH -> BTC then we're making the following trades
    # BTC/ETC base ETC quote BTC buying ETC (base)  = asks
    # ETC/ETH base ETC quote ETH buying ETH (quote) = bids
    # ETH/BTC base ETH quote BTC buying BTC (quote) = bids
    path = [exchanges[0].base_currency]
    path.extend([e.quote_currency for e in exchanges[1:]])
    # BTC -> ['ETC', 'ETH', 'BTC']

    for count, exchange in enumerate(exchanges[1:]):

        buying = path[count]
        base = exchange.base_currency
        quote = exchange.quote_currency
        if buying == quote:
            buy_type = 'bids'
        else:
            buy_type = 'asks'
        buys.append(match_order_book(exchange, to_sell=buys[count], buy_type=buy_type))
        if buy_type == 'asks':
            logging.debug('Sold {} {} for {} {}'.format(buys[count], base, buys[count + 1], quote))
        else:
            logging.debug('Sold {} {} for {} {}'.format(buys[count], quote, buys[count + 1], base))

    diff = buys[len(buys) - 1] - initial_cost

    # fees
    profit = (diff - initial_cost * Decimal('0.006')) * Decimal(fiat_rate)

    logging.debug('Profit is {} GBP'.format(profit))

    logging.debug(time.time() - start_time)
    exit(0)
    # bellend(currencies, exchanges, pairs)


def bellend(currencies, exchanges, pairs):
    graph = construct_rate_graph(currencies, exchanges)
    paths = []

    for key in graph:
        path = bellman_ford(graph, key)
        if path not in paths and not None:
            paths.append(path)

    for path in paths:
        if path == None:
            logging.debug("No opportunity here :(")
        else:
            trade_pair = '{}-{}'.format(path[0], path[1])
            fiat_rate = get_fiat_rate(path[0])
            try:
                exchange = exchanges[pairs.index(trade_pair)]
            except ValueError:
                trade_pair = '{}-{}'.format(path[1], path[0])
                exchange = exchanges[pairs.index(trade_pair)]

            # i.e. LTC
            if exchange.base_currency == path[0]:
                money = exchange.lowest_ask['volume']
            else:
                money = exchange.lowest_ask['volume'] * exchange.lowest_ask['price']
            fiat_amount = fiat_rate * money
            logging.debug(
                "Starting with %(money)s in %(currency)s (%(fiat)s in fiat)" % {"money": money, "currency": path[0],
                                                                                "fiat": fiat_amount})

            money_start = money
            for i, value in enumerate(path):
                if i + 1 < len(path):
                    start = path[i]
                    end = path[i + 1]

                    rate = Decimal(math.exp(-graph[start][end]))
                    money = rate * money
                    logging.debug(
                        "%(start)s to %(end)s at %(rate)f = %(money)f" % {"start": start, "end": end, "rate": rate,
                                                                          "money": money})
            diff = (money - money_start) * fiat_rate
            logging.debug('Diff is {} GBP {} % of {}'.format(diff, diff / fiat_amount * 100, fiat_amount))

        logging.debug("\n")


if __name__ == "__main__":  # pragma: nocoverage
    process()
