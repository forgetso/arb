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
from collections import deque


def match_order_book(exchange, to_sell, buy_type, sell_symbol):
    depth = 0
    to_buy = 0
    transactions = []
    try:
        # if pair is ETH-BTC, volume is in ETH, price is in BTC
        # BTC volume is volume * price
        # if buy type is asks, we are selling BTC (to_sell) for ETH (to_buy)
        # if buy type is bids, we are selling ETH (to_sell) for BTC (to_buy)
        orders = getattr(exchange, buy_type)
        transactions = []
        assert exchange.bids[0]['price'] < exchange.asks[0]['price']
        while to_sell > 0:
            buy = 0
            price = orders[depth]['price']
            volume = orders[depth]['volume']
            # each one of these buys and sells would need to be stored and then executed individually
            if sell_symbol == exchange.base_currency:
                sell_available = volume
                if sell_available > to_sell:
                    buy = to_sell / sell_available * price * volume
                    to_sell = 0
                else:
                    to_sell -= sell_available
                    buy = price * volume
            if sell_symbol == exchange.quote_currency:
                sell_available = volume * price
                if sell_available > to_sell:
                    buy = to_sell / sell_available * volume
                    to_sell = 0
                else:
                    to_sell -= sell_available
                    buy = orders[depth]['volume']
            to_buy += buy
            transactions.append({'buy': buy, 'price': price})
            depth += 1

    except IndexError as e:
        print(e)
        logging.debug(
            'Not enough {} to complete trade. {} {}'.format(buy_type, len(getattr(exchange, buy_type)), buy_type))

    return to_buy, transactions


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
    # from app.tools.all_combinations import trade_paths
    # print(trade_paths())
    # exit(0)

    pairs = ['LTC-BTC', 'LTC-ETH', 'ETH-BTC']
    random.shuffle(pairs)
    # print(pairs)
    logging.debug('chosen pairs {}'.format(pairs))

    exchange_count = len(pairs)
    random_exchanges = choose_random_exchanges(number=len(pairs), duplicates=True)
    for exchange in random_exchanges:
        exchanges.append(dynamically_import_exchange(exchange)('xxx'))

    markets = load_currency_pairs()

    currencies = []

    previous_exchange = None
    for count, pair in enumerate(pairs):
        exchanges[count].set_trade_pair(pair, markets)
        currencies.append(exchanges[count].base_currency)
        currencies.append(exchanges[count].quote_currency)

    trade_path = deque()
    for current_exchange in exchanges:

        if previous_exchange is not None:
            curr_from, curr_to, buy_type = find_trade_path(previous_exchange, current_exchange)
            # this is actually the last trade
            trade_path.append({'from': curr_from,
                               'to': curr_to,
                               'buy_type': buy_type,
                               'exchange': current_exchange,
                               'from_symbol': getattr(current_exchange, curr_from),
                               'to_symbol': getattr(current_exchange, curr_to)
                               })
        else:
            curr_from, curr_to, buy_type = find_trade_path(exchanges[exchange_count - 1], current_exchange)
            # all other trades are inserted before the last trade
            trade_path.appendleft({'from': curr_from,
                                   'to': curr_to,
                                   'buy_type': buy_type,
                                   'exchange': current_exchange,
                                   'from_symbol': getattr(current_exchange, curr_from),
                                   'to_symbol': getattr(current_exchange, curr_to)
                                   })
        previous_exchange = current_exchange

    # pprint.pprint(trade_path)
    for p in trade_path:
        logging.debug('{} to {}'.format(getattr(p['exchange'], p['from']), getattr(p['exchange'], p['to'])))

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

    # set up the volume that we need to sell for the first transaction
    orders = getattr(trade_path[0]['exchange'], trade_path[0]['buy_type'])
    to_sell = orders[0]['volume'] * orders[0]['price']
    fiat_rate = get_fiat_rate(trade_path[0]['from_symbol'])
    initial_cost = to_sell

    # print(orders[0])
    # now loop all the transactions in the transaction path
    for p in trade_path:
        logging.debug('To Sell {} {}'.format(to_sell, p['from_symbol']))
        # pprint.pprint(p)
        buy_type = p['buy_type']
        exchange = p['exchange']
        orders = getattr(p['exchange'], p['buy_type'])
        # print(orders[0])
        bought, txs = match_order_book(exchange, to_sell, buy_type, sell_symbol=p['from_symbol'])
        # print(txs)

        computed_sell = sum([tx['buy'] * tx['price'] for tx in txs])
        #logging.debug('Computed sell {}'.format(computed_sell))
        logging.debug('Bought {} {} using {} {}'.format(bought, p['to_symbol'], to_sell, p['from_symbol']))
        try:
            assert computed_sell / to_sell < 1.001
        except AssertionError as e:
            print(orders[0])
            print(txs)
            raise Exception('Computed sell differs to sell value!')

        to_sell = bought
        buys.append(bought)

    diff = buys[len(buys) - 1] - initial_cost
    # fees
    profit = (diff - initial_cost * Decimal('0.006')) * Decimal(fiat_rate)

    logging.debug('Profit is {} GBP'.format(profit))

    logging.debug('Time taken {}s'.format(time.time() - start_time))
    #bellend(currencies, exchanges, pairs)


def find_trade_path(previous, current):
    # find out where we're starting and finishing
    result = None
    # logging.debug('Going from {} to {}'.format(previous.trade_pair, current.trade_pair))
    # there can only be one link between two exchanges, e.g. ETH BTC | LTC BTC. Link is BTC
    if previous.base_currency == current.quote_currency:
        # logging.debug(
        #     'Previous Base {} is the same as current Quote {}'.format(previous.base_currency, current.quote_currency))
        result = 'quote_currency', 'base_currency', 'asks'
    elif previous.quote_currency == current.quote_currency:
        # logging.debug(
        #     'Previous Quote {} is the same as current Quote {}'.format(previous.quote_currency, current.quote_currency))
        result = 'quote_currency', 'base_currency', 'asks'
    elif previous.base_currency == current.base_currency:
        # logging.debug(
        #     'Previous Base {} is the same as current Base {}'.format(previous.base_currency, current.base_currency))
        result = 'base_currency', 'quote_currency', 'bids'
    elif previous.quote_currency == current.base_currency:
        # logging.debug(
        #     'Previous Quote {} is the same as current Base {}'.format(previous.quote_currency, current.base_currency))
        result = 'base_currency', 'quote_currency', 'bids'
    # logging.debug(result)
    return result


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
            fiat_rate = fiat_rate(path[0])
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
