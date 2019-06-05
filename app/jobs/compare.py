import argparse
import logging
import itertools
from app.lib.setup import setup_environment, load_currency_pairs, choose_two_random_exchanges, \
    dynamically_import_exchange
from app.lib.errors import ErrorTradePairDoesNotExist
from app.settings import FIAT_DEFAULT_SYMBOL, FIAT_ARBITRAGE_MINIMUM, LOGLEVEL, EXCHANGES, FIAT_REPLENISH_AMOUNT
from app.lib.jobqueue import return_value_to_stdout
from decimal import Decimal
from app.lib.db import store_audit, get_fiat_rates
from app.lib.common import round_decimal_number, decimal_as_string


def compare(cur_x, cur_y, markets, jobqueue_id):
    arbitrages = []
    viable_arbitrages = []
    replenish_jobs = []
    result = {'downstream_jobs': []}

    apis_trade_pair_valid = exchange_selection(cur_x, cur_y, markets, EXCHANGES, jobqueue_id)

    if len(apis_trade_pair_valid) < 2:
        # return early as there will be no arbitrage possibility with only one or zero exchanges
        return_value_to_stdout(result)
        return result

    fiat_rates = get_fiat_rates()
    try:
        fiat_rate = round_decimal_number(fiat_rates[cur_y][FIAT_DEFAULT_SYMBOL], 2)
        logging.debug('Fiat rate is {}'.format(fiat_rate))
    except:
        raise CompareError('Fiat Rate for {} is not present in db'.format(cur_y))

    # get the order book from each api
    for exchange in apis_trade_pair_valid:
        exchange.order_book()

    # generate a unique list of permutations for comparison [[buy, sell], [buy, sell], ...]
    exchange_permutations = list(itertools.permutations(apis_trade_pair_valid, 2))

    # first sort out the volumes in each exchange object
    exchange_permutations_fixed = []
    for exchange_permutation in exchange_permutations:
        exchange_permutations_fixed.append(equalise_buy_and_sell_volumes(exchange_permutation))

    # determine whether buying and selling across each permutation will result in a profit > FIAT_ARBITRAGE_MINIMUM
    for exchange_permutation in exchange_permutations_fixed:
        exchange_buy, exchange_sell = exchange_permutation
        arbitrage = find_arbitrage(exchange_buy, exchange_sell, fiat_rate)
        if arbitrage:
            arbitrages.append(arbitrage)
            exchange_names = [arbitrage['buy'].name, arbitrage['sell'].name]
            profit_audit_record = profit_audit(arbitrage['profit'],
                                               arbitrage['buy'].trade_pair_common,
                                               exchange_names)
            store_audit(profit_audit_record)

    for arbitrage in arbitrages:
        arbitrage['buy'].get_balances()
        arbitrage['sell'].get_balances()
        # first, make sure we do not have zero of the currency we're trying to sell
        # send more of the currency to that exchange if there is a zero balance
        replenish_jobs = check_zero_balances(arbitrage)
        if not replenish_jobs:
            viable_arbitrages = determine_arbitrage_viability(arbitrage, fiat_rate)

    # result is a list of downstream jobs to add to the queue
    result['downstream_jobs'] = viable_arbitrages + replenish_jobs
    for job in result['downstream_jobs']:
        job['job_args']['jobqueue_id'] = jobqueue_id

    logging.debug('Returning {}'.format(result))

    # make sure the job queue executor can access the result by writing to stdout
    return_value_to_stdout(result)

    return result


def check_zero_balances(arbitrage):
    replenish_jobs = []
    exchange_buy = arbitrage['buy']
    exchange_sell = arbitrage['sell']
    exchange_balance = exchange_buy.balances.get(exchange_buy.quote_currency, 0)

    # if we dont have any BTC then we cannot buy any ETH, replenish BTC
    if exchange_balance == 0:
        replenish_jobs.append(replenish_job(exchange_buy.name, exchange_buy.quote_currency))

    exchange_balance = exchange_sell.balances.get(exchange_buy.quote_currency, 0)
    # if we dont have any ETH then we cannot buy any BTC, replenish ETH
    if exchange_balance == 0:
        replenish_jobs.append(replenish_job(exchange_buy.name, exchange_buy.base_currency))

    return replenish_jobs


def equalise_buy_and_sell_volumes(exchange_permutation):
    # Take the volume of the highest bid from an exchange and set it as the volume we should buy
    # as we should not buy more than we can sell
    # Example
    # lowest ask: we can buy 4 BTC (volume) at 99 ETH (price) per BTC
    # highest bid: but we can only sell 3 BTC (volume) at 100 ETH (price) per BTC
    exchange_buy, exchange_sell = exchange_permutation
    volume_equal = exchange_buy.lowest_ask['volume']
    volume_sell = exchange_sell.highest_bid['volume']
    volume_buy = exchange_buy.lowest_ask['volume']
    if volume_sell < volume_buy:
        volume_equal = volume_sell
    exchange_buy.lowest_ask['volume'] = volume_equal
    exchange_sell.highest_bid['volume'] = volume_equal

    return (exchange_buy, exchange_sell)


def set_maximum_trade_volume(volume, price, fiat_rate):
    # We don't want to make trades more than 100 GBP at a time
    # 3 ETH at 0.1 BTC * 8000 GBP = 2400 GBP > 100 GBP => 3 * (100 / 2400) is the volume
    total_cost_fiat = volume * price * fiat_rate
    if total_cost_fiat > FIAT_REPLENISH_AMOUNT:
        volume = FIAT_REPLENISH_AMOUNT / total_cost_fiat * volume
        logging.debug('Changing volume to {} '.format(volume))
    return volume


def determine_arbitrage_viability(arbitrage, fiat_rate):
    viable_arbitrages = []
    exchange_buy = arbitrage['buy']
    exchange_sell = arbitrage['sell']
    profit = arbitrage['profit']
    revalidate = False
    revalidation_result = None

    # buy #
    price_buy = exchange_buy.lowest_ask['price']
    volume_base = exchange_buy.lowest_ask['volume']
    exchange_balance = exchange_buy.balances.get(exchange_buy.quote_currency, 0)

    # if we have some BTC but not enough to buy required ETH then try to use what BTC we have
    if Decimal(0) < exchange_balance < volume_base * price_buy:
        # will try and use the btc we have instead
        volume_base = exchange_balance / price_buy * volume_base
        revalidate = True

    # sell #
    # we may not have had enough BTC to buy all the offered ETH, therefore volume may be lower
    price_sell = exchange_sell.highest_bid['price']
    volume_base = min(exchange_sell.lowest_ask['volume'], volume_base)

    exchange_balance = exchange_sell.balances.get(exchange_sell.base_currency, 0)

    # we have some ETH but not as much as we need to sell [volume]
    if Decimal(0) < exchange_balance < volume_base:
        volume_base = exchange_balance
        revalidate = True

    # so we now have a final volume_base. we need to recheck trade validity
    exchange_buy.lowest_ask['volume'] = volume_base
    exchange_sell.highest_bid['volume'] = volume_base

    # use the same function as before to check the modified trades for profitability
    if revalidate:
        revalidation_result = find_arbitrage(exchange_buy, exchange_sell, fiat_rate=fiat_rate)

    # if the trades were good first time round or the altered trades would generate enough profit
    if not revalidate or revalidation_result:
        buy_transact = transact_job(exchange_buy.name, exchange_buy.trade_pair_common, volume_base, price_buy, 'buy',
                                    profit)
        sell_transact = transact_job(exchange_sell.name, exchange_sell.trade_pair_common, volume_base, price_sell,
                                     'sell',
                                     profit)
        viable_arbitrages.append(buy_transact)
        viable_arbitrages.append(sell_transact)

    return viable_arbitrages


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

    if exchange_x.lowest_ask and exchange_y.highest_bid:
        if exchange_x.lowest_ask['price'] < exchange_y.highest_bid['price']:

            exchange_x, exchange_y, profit = calculate_profit_and_volume(exchange_x, exchange_y, fiat_rate)

            if profit > FIAT_ARBITRAGE_MINIMUM:
                result = {'buy': exchange_x, 'sell': exchange_y, 'profit': profit}
                logging.info(
                    msg='You can buy for {} on {} and sell for {} on {} for profit {} {}'.format(
                        exchange_x.lowest_ask['price'],
                        exchange_x.name,
                        exchange_y.highest_bid['price'],
                        exchange_y.name,
                        profit,
                        FIAT_DEFAULT_SYMBOL))

    return result


def calculate_profit_and_volume(exchange_buy, exchange_sell, fiat_rate):
    try:
        volume = exchange_buy.lowest_ask['volume']
        price_sell = exchange_sell.highest_bid['price']
        price_buy = exchange_buy.lowest_ask['price']
    except KeyError as e:
        raise CompareError('Error retrieving volume/price data from exchange object: {}'.format(e))

    trade_valid_sell, price_sell, volume_sell = exchange_sell.trade_validity(currency=exchange_sell.base_currency,
                                                                             price=price_sell, volume=volume)
    trade_valid_buy, price_buy, volume_buy = exchange_buy.trade_validity(currency=exchange_buy.base_currency,
                                                                         price=price_buy, volume=volume)
    if not trade_valid_buy or not trade_valid_sell:
        raise ValueError('Invalid Trade!')

    volume = set_maximum_trade_volume(volume, price_buy, fiat_rate)

    try:

        fee = exchange_sell.fee * volume * price_sell + exchange_buy.fee * volume * price_buy
    except:
        raise Exception(type(volume), type(price_sell), type(price_buy), type(exchange_buy.fee),
                        type(exchange_sell.fee))

    profit = ((price_sell - price_buy) * volume - fee) * fiat_rate

    exchange_buy.lowest_ask['volume'] = volume
    exchange_sell.highest_bid['volume'] = volume

    return exchange_buy, exchange_sell, profit


# randomly select the names of two exchanges and then check if the trade pair exists in both exchanges
# if the trade pair is not in both exchanges, repeat until we have a pair, up to 10 times
# TODO construct the cross sections of trade pairs and exchanges and randomly select from it instead
def exchange_selection(cur_x, cur_y, markets, exchanges, jobqueue_id, directory=None):
    trade_pair = '{}-{}'.format(cur_x, cur_y)
    potential_exchanges = []
    apis_trade_pair_valid = []

    for exchange in markets:
        if trade_pair in markets[exchange] and exchange in exchanges:
            potential_exchanges.append(exchange)

    if len(potential_exchanges) < 2:
        # there are not enough exchanges that trade this pair
        return apis_trade_pair_valid
    if len(potential_exchanges) == 2:
        random_exchanges = potential_exchanges
    else:

        random_exchanges = choose_two_random_exchanges(potential_exchanges)

    logging.debug('exchanges chosen {}'.format(random_exchanges))

    imported_exchanges = []
    for exchange in random_exchanges:
        imported_exchanges.append(dynamically_import_exchange(exchange, directory)(jobqueue_id))

    # make our trade pair equal to a list [ETH, USD]
    trade_pair_list = [cur_x, cur_y]
    trade_pair = check_trade_pair(trade_pair_list)

    # set the trade pair for each api
    # this error should technically not be reached
    for exchange in imported_exchanges:
        try:
            exchange.set_trade_pair(trade_pair, markets)
        except ErrorTradePairDoesNotExist:
            logging.info('{} does not trade {}'.format(exchange.name, trade_pair))
            continue
        apis_trade_pair_valid.append(exchange)

    return apis_trade_pair_valid


def replenish_job(exchange_name, currency):
    return {
        'job_type': 'REPLENISH',
        'job_args': {
            'exchange': exchange_name,
            'currency': currency,
        }
    }


def profit_audit(profit, exchange_names, trade_pair):
    return {
        'type': 'profit',
        'profit': float(round(profit, 2)),
        'currency': FIAT_DEFAULT_SYMBOL,
        'exchange_names': list(exchange_names),
        'trade_pair': trade_pair
    }


def transact_job(exchange_name, trade_pair, volume, price, buy_type, profit):
    job = {
        'job_type': 'TRANSACT',
        'job_args': {
            'exchange': exchange_name,
            'trade_pair_common': trade_pair,
            'volume': decimal_as_string(volume),
            'price': decimal_as_string(price),
            'type': buy_type,

        },
        'job_info': {'profit': float(round(profit, 2)), 'currency': FIAT_DEFAULT_SYMBOL}}
    return job


def setup():
    parser = argparse.ArgumentParser(description='Process some currencies.')
    parser.add_argument('curr_x', type=str, help='Currency to compare')
    parser.add_argument('curr_y', type=str, help='Currency to compare')
    parser.add_argument('jobqueue_id', type=str, help='Jobqueue Id')
    parser.add_argument('--setup', action='store_true')
    parser.add_argument('--setuponly', action='store_true',
                        help='Only run the setup process, not the comparison process')
    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)

    # configure a bunch of stuff for running like currency pairs, database, ... TODO make this a class?
    if args.setup and not args.setuponly:
        setup_environment(args.jobqueue_id)

    if args.setuponly:
        setup_environment(args.jobqueue_id)
        exit()

    markets = load_currency_pairs()

    output = compare(args.curr_x, args.curr_y, markets, args.jobqueue_id)
    return output


class CompareError(Exception):
    pass


if __name__ == "__main__":  # pragma: nocoverage
    setup()
