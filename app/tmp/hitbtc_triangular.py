from app.wraps.wrap_hitbtc import hitbtc
from app.wraps.wrap_binance import binance
from app.wraps.wrap_bittrex import bittrex
from app.lib.setup import load_currency_pairs
from app.jobs.compare import run_exchange_functions_as_threads, get_fiat_rate
from decimal import Decimal
import logging
import pprint
import time
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
        assert bids[0]['price'] < asks[0]['price']
        while to_sell >= 0:
            if buy_type == 'asks':
                # each one of these buys and sells would need to be stored and then executed individually
                to_sell -= asks[depth]['volume'] * asks[depth]['price']
                to_buy += asks[depth]['volume']
            elif buy_type == 'bids':
                to_buy += bids[depth]['volume'] * bids[depth]['price']
                to_sell -= bids[depth]['volume']
            depth += 1

        if to_sell < 0:
            if buy_type == 'asks':
                # Trying to buy too much ETH. Take some off, equivalent to how much we went past zero
                to_buy -= -to_sell / asks[depth]['price']
            elif buy_type == 'bids':
                # Trying to buy too much BTC. Take some off, equivalent to how much we went past zero
                to_buy -= -to_sell * bids[depth]['price']
    except IndexError:
        print('Not enough {} to complete trade. {} {}'.format(buy_type, len(getattr(exchange, buy_type)), buy_type))

    return to_buy


from math import log


def bellman_ford(graph):
    transformed_graph = [[-log(edge) for edge in row] for row in graph]
    pprint.pprint(transformed_graph)

    # Pick any source vertex -- we can run Bellman-Ford from any vertex and
    # get the right result
    source = 0
    n = len(transformed_graph)

    # set the initial distance to each node to be infinity, so any distance found will be less
    min_dist = [float('inf')] * n

    min_dist[source] = 0

    # Relax edges |V - 1| times
    for i in range(n - 1):
        for v in range(n):
            for w in range(n):
                if min_dist[w] > min_dist[v] + transformed_graph[v][w]:
                    min_dist[w] = min_dist[v] + transformed_graph[v][w]

    # If we can still relax edges, then we have a negative cycle
    for v in range(n):
        for w in range(n):
            if min_dist[w] > min_dist[v] + transformed_graph[v][w]:
                return True

    return False


def construct_rate_graph(currencies, exchanges):
    # Graph
    # [[inf, Decimal('0.05387000'), Decimal('0.0012800')],
    #  [Decimal('0.05371000'), inf, Decimal('0.02378800')],
    #  [Decimal('0.0012726'), Decimal('0.02378700'), inf]]
    # if currencies = ['ETH','BTC','REP'] then price from ETH to BTC is 0.05387000

    graph = [[float('inf') for _ in currencies] for _ in currencies]

    for count, row in enumerate(graph):
        for exchange in exchanges:
            if count == currencies.index(exchange.base_currency):
                graph[count][currencies.index(exchange.quote_currency)] = exchange.lowest_ask['price']
            if count == currencies.index(exchange.quote_currency):
                graph[count][currencies.index(exchange.base_currency)] = exchange.highest_bid['price']

    logging.debug('Currencies are {} '.format(currencies))

    pprint.pprint(graph)
    return graph


def process():

    # trade pairs are BUY-SELL
    # so we want BUY LTC, SELL LTC, BUY ETH
    pairs = ['REP-ETH', 'REP-BTC', 'ETH-BTC']
    exchanges = []
    exchanges.append(binance(jobqueue_id='xx'))
    exchanges.append(hitbtc(jobqueue_id='xx'))
    exchanges.append(binance(jobqueue_id='xx'))

    markets = load_currency_pairs()

    fiat_rate = fiat_rate('ETH')

    for count, pair in enumerate(pairs):
        exchanges[count].set_trade_pair(pair, markets)
    run_exchange_functions_as_threads(exchanges, 'order_book')
    start = time.time()
    # graph = construct_rate_graph(['REP', 'ETH', 'BTC'], exchanges)
    # print(bellman_ford(graph))


    initial_depth = 1
    ltc_bought = sum([x['volume'] for x in exchanges[0].asks[0:initial_depth]])
    initial_eth = sum([x['volume'] * x['price'] for x in exchanges[0].asks[0:initial_depth]])

    initial_fiat = fiat_rate * initial_eth

    print('Sold {} ETH for {} LTC'.format(initial_eth, ltc_bought))

    btc_bought = match_order_book(exchanges[1], ltc_bought, 'bids')

    print('Sold {} LTC for {} BTC'.format(ltc_bought, btc_bought))

    eth_bought = match_order_book(exchanges[2], btc_bought, 'asks')

    print('Sold {} BTC for {} ETH'.format(btc_bought, eth_bought))

    diff = eth_bought - initial_eth

    # fees
    profit = (diff - initial_eth * Decimal('0.006')) * Decimal(fiat_rate)

    print('Profit is {}'.format(profit))

    print(time.time()-start)
    exit(0)
process()
