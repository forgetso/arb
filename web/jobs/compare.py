import argparse
import logging
import itertools
from web.lib.setup import setup_environment, get_exchanges, load_currency_pairs, get_current_fiat_rate
from web.lib.errors import ErrorTradePairDoesNotExist
from web.settings import FIAT_DEFAULT_SYMBOL, FIAT_ARBITRAGE_MINIMUM, LOGLEVEL
from web.lib.jobqueue import return_value_to_stdout
from decimal import Decimal


def compare(cur_x, cur_y, markets, fiat_rate):
    exchanges = get_exchanges()
    apis_trade_pair_valid = []
    arbitrages = []
    viable_arbitrages = []
    replenish_jobs = []
    result = {'downstream_jobs': []}

    # make our trade pair equal to a list [ETH, USD]
    trade_pair_list = [cur_x, cur_y]
    trade_pair = check_trade_pair(trade_pair_list)

    # set the trade pair for each api
    for exchange in exchanges:
        try:
            exchange.set_trade_pair(trade_pair, markets)
        except ErrorTradePairDoesNotExist:
            logging.info('{} does not trade {}'.format(exchange.name, trade_pair))
            continue
        apis_trade_pair_valid.append(exchange)

    if len(exchanges) < 2:
        # return early as there will be no arbitrage possibility with only one exchange
        return_value_to_stdout(result)
        return

    # get the order book from each api
    for exchange in apis_trade_pair_valid:
        exchange.order_book()

    # generate a unique list of pairs for comparison
    exchange_combinations = itertools.combinations(apis_trade_pair_valid, 2)

    for exchange_combination in exchange_combinations:
        arbitrage = find_arbitrage(exchange_combination[0], exchange_combination[1], fiat_rate)
        if arbitrage:
            arbitrages.append(arbitrage)

    if arbitrages:
        for arbitrage in arbitrages:
            arbitrage['buy'].get_balances()
            arbitrage['sell'].get_balances()

        logging.debug(arbitrage['sell'].balances)

        viable_arbitrages, replenish_jobs = determine_arbitrage_viability(arbitrages)

    # result is a list of downstream jobs to add to the queue
    result['downstream_jobs'] = viable_arbitrages + replenish_jobs
    logging.debug('Returning {}'.format(result))

    # make sure the job queue executor can access the result by writing to stdout
    return_value_to_stdout(result)

    return result


def determine_arbitrage_viability(arbitrages):
    viable_arbitrages = []
    replenish_jobs = []
    currency = None
    sell_volume = None
    for arbitrage in arbitrages:
        if arbitrage['profit'] > FIAT_ARBITRAGE_MINIMUM:
            logging.info('Viable arbitrage found')
            for buy_type in ['buy', 'sell']:
                exchange = arbitrage[buy_type]
                if buy_type == 'buy':
                    price = exchange.lowest_ask['price']
                    volume = exchange.lowest_ask['volume']
                    if volume * price > exchange.balances.get(exchange.quote_currency):
                        volume = exchange.balances.get(exchange.quote_currency)
                        currency = exchange.quote_currency
                    # buy is always first in the loop so this is ok
                    sell_volume = volume
                else:
                    price = exchange.highest_bid['price']
                    # we only want to sell the amount we managed to buy
                    volume = sell_volume
                    currency = exchange.base_currency

                    if volume > exchange.balances.get(exchange.base_currency):
                        volume = exchange.balances.get(exchange.base_currency)
                        # therefore we also only want to buy this much
                        viable_arbitrages[0]['job_args']['volume'] = decimal_as_string(volume)

                # the account has none of this currency, need to replenish
                if volume == 0:
                    replenish_jobs.append({
                        'job_type': 'REPLENISH',
                        'job_args': {
                            'exchange': exchange.name,
                            'currency': currency
                        }
                    })
                    viable_arbitrages = []
                    break

                job = {
                    'job_type': 'TRANSACT',
                    'job_args': {
                        'exchange': exchange.name,
                        'trade_pair_common': exchange.trade_pair_common,
                        'volume': decimal_as_string(volume),
                        'price': decimal_as_string(price),
                        'type': buy_type,

                    }}
                viable_arbitrages.append(job)

    return viable_arbitrages, replenish_jobs


def decimal_as_string(number):
    # float returns stupid strings like 4.5e-05
    # float also contains rounding errors
    # so we make things into Decimals
    # Decimals automatically round to 20 places or something, even if this includes loads of trailing zeroes
    # so we use normalize to strip the trailing zeroes
    try:
        result = str(Decimal(number).normalize())
    except:
        raise TypeError(
            'Decimal as string expects a numeric values to be converted to a decimal. You passed {} {}'.format(
                number,
                type(number)))
    return result


def check_trade_pair(trade_pair):
    result = None
    # trade pair is a list of two currencies e.g. [ETH, USD]
    if not isinstance(trade_pair, list):
        raise TypeError('trade pair must be a list: {}'.format(trade_pair))
    if len(trade_pair) != 2:
        raise ValueError('trade pair length must be 2')
    try:
        result = '-'.join(trade_pair)
    except TypeError:
        raise TypeError('trade pair must be a pair of strings for concatenation')

    if not result:
        raise Exception('trade pair error - unhandled error')

    return result


def find_arbitrage(exchange_x, exchange_y, fiat_rate):
    result = {}
    # TODO ensure that volume is above minimum threshold for exchange
    # try:
    if exchange_x.lowest_ask and exchange_y.highest_bid:
        if exchange_x.lowest_ask['price'] < exchange_y.highest_bid['price']:

            profit = calculate_profit(exchange_x, exchange_y, fiat_rate)
            result = {'buy': exchange_x, 'sell': exchange_y, 'profit': profit}
            if profit > 0:
                logging.info(
                    msg='You can buy for {} on {} and sell for {} on {} for profit {} {}'.format(
                        exchange_x.lowest_ask,
                        exchange_x.name,
                        exchange_y.highest_bid,
                        exchange_y.name,
                        profit,
                        FIAT_DEFAULT_SYMBOL))

    if exchange_y.lowest_ask and exchange_x.highest_bid:
        if exchange_y.lowest_ask['price'] < exchange_x.highest_bid['price']:

            profit = calculate_profit(exchange_y, exchange_x, fiat_rate)
            result = {'buy': exchange_y, 'sell': exchange_x, 'profit': profit}
            if profit > 0:
                logging.info(
                    msg='You can buy for {} on {} and sell for {} on {} for profit {} {}'.format(
                        exchange_y.lowest_ask,
                        exchange_y.name,
                        exchange_x.highest_bid,
                        exchange_x.name,
                        profit,
                        FIAT_DEFAULT_SYMBOL))
    # except TypeError:
    #     logging.debug('One of the exchanges had either no bids or no asks')
    #     pass

    return result


def calculate_profit(exchange_buy, exchange_sell, fiat_rate):
    try:
        volume = exchange_buy.lowest_ask['volume']
        price_sell = exchange_sell.highest_bid['price']
        price_buy = exchange_buy.lowest_ask['price']
        try:

            fee = exchange_sell.fee * volume * price_sell + exchange_buy.fee * volume * price_buy
        except:
            raise Exception(type(volume), type(price_sell), type(price_buy), type(exchange_buy.fee), type(exchange_sell.fee))

        if exchange_sell.highest_bid['volume'] < exchange_buy.lowest_ask['price']:
            volume = exchange_sell.highest_bid['volume']
        fees = price_sell * volume * fee
        profit = ((price_sell - price_buy) * volume - fees) * fiat_rate
    except Exception as e:
        raise Exception(e)

    return profit


def setup():
    parser = argparse.ArgumentParser(description='Process some currencies.')
    parser.add_argument('curr_x', type=str, help='Currency to compare')
    parser.add_argument('curr_y', type=str, help='Currency to compare')
    parser.add_argument('fiat_rate', type=float, help='The FIAT rate of BTC to work out profit')
    parser.add_argument('--setup', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)

    # configure a bunch of stuff for running like currency pairs, database, ... TODO make this a class?
    if args.setup:
        setup_environment()

    markets = load_currency_pairs()

    if args.curr_y != 'BTC':
        fiat_rate = 1
    else:
        fiat_rate = Decimal(args.fiat_rate)

    output = compare(args.curr_x, args.curr_y, markets, fiat_rate)
    return output


if __name__ == "__main__":  # pragma: nocoverage
    setup()
