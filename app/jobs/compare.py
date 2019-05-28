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
from app.lib.common import round_decimal_number

from bson import json_util
import json


def compare(cur_x, cur_y, markets, jobqueue_id):
    arbitrages = []
    viable_arbitrages = []
    replenish_jobs = []
    result = {'downstream_jobs': []}

    apis_trade_pair_valid = exchange_selection(cur_x, cur_y, markets, jobqueue_id)

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

    # generate a unique list of pairs for comparison
    # TODO this is now invalid as we only pass 2 exchanges. Remove?
    exchange_combinations = itertools.combinations(apis_trade_pair_valid, 2)

    for exchange_combination in exchange_combinations:
        arbitrage = find_arbitrage(exchange_combination[0], exchange_combination[1], fiat_rate)
        if arbitrage:
            arbitrages.append(arbitrage)

    if arbitrages:
        for arbitrage in arbitrages:
            arbitrage['buy'].get_balances()
            # logging.debug('BUY balances {}'.format(arbitrage['buy'].balances))
            arbitrage['sell'].get_balances()
            # logging.debug('SELL balances {}'.format(arbitrage['sell'].balances))

        viable_arbitrages, replenish_jobs, profit_audit = determine_arbitrage_viability(arbitrages)

        if profit_audit:
            # store details of potential profits to work out if all of this is worthwhile
            store_audit(profit_audit)

    # result is a list of downstream jobs to add to the queue
    result['downstream_jobs'] = viable_arbitrages + replenish_jobs
    for job in result['downstream_jobs']:
        job['job_args']['jobqueue_id'] = jobqueue_id

    logging.debug('Returning {}'.format(result))

    # make sure the job queue executor can access the result by writing to stdout
    return_value_to_stdout(result)

    return result


def determine_arbitrage_viability(arbitrages):
    viable_arbitrages = []
    profit_audit = {}
    replenish_jobs = []
    currency = None
    sell_volume = None
    exchange_names = set()
    store_profit_audit = False
    trade_pair = ''
    profit = None
    for arbitrage in arbitrages:
        if arbitrage['profit'] > FIAT_ARBITRAGE_MINIMUM:
            logging.info('Viable arbitrage found')
            profit = arbitrage['profit']

            for buy_type in ['buy', 'sell']:
                exchange = arbitrage[buy_type]
                exchange_names |= set((exchange.name,))
                if buy_type == 'buy':
                    price = exchange.lowest_ask['price']
                    volume = exchange.lowest_ask['volume']
                    exchange_balance = exchange.balances.get(exchange.quote_currency, 0)
                    logging.debug(exchange_balance)
                    if 0 < exchange_balance < volume * price:
                        volume = exchange_balance
                    # buy is always first in the loop so this is ok
                    sell_volume = volume
                else:
                    price = exchange.highest_bid['price']
                    # we only want to sell the amount we managed to buy
                    volume = sell_volume
                    currency = exchange.base_currency

                    logging.debug('Exchange {} currency balance {}'.format(exchange.name,
                                                                           exchange.balances.get(
                                                                               exchange.base_currency)))
                    exchange_balance = exchange.balances.get(exchange.base_currency, 0)
                    if Decimal(0) < exchange_balance < volume * price:
                        volume = exchange_balance
                        # therefore we also only want to buy this much
                        viable_arbitrages[0]['job_args']['volume'] = decimal_as_string(volume)

                logging.debug('Confirming validity of price {}  volume {} buy_type {}'.format(price, volume, buy_type))
                trade_valid, price, volume = exchange.trade_validity(price=price, volume=volume)

                if not trade_valid:
                    logging.debug('INVALID TRADE! {} {} {}'.format(exchange.name, price, volume))
                    viable_arbitrages = []
                    break

                # store a record of this trade so that we can analyse later
                store_profit_audit = True
                trade_pair = exchange.trade_pair_common

                # the account has none of this currency, need to replenish
                # this only matters when we're trying to SELL a currency
                if buy_type == 'sell':
                    if volume == 0 or volume < exchange.min_trade_size:
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

                    },
                    'job_info': {'profit': float(round(arbitrage['profit'], 2)), 'currency': FIAT_DEFAULT_SYMBOL}}
                viable_arbitrages.append(job)

    if store_profit_audit:
        profit_audit = {
            'profit': float(round(profit, 2)),
            'currency': FIAT_DEFAULT_SYMBOL,
            'exchange_names': list(exchange_names),
            'trade_pair': trade_pair
        }

    return viable_arbitrages, replenish_jobs, profit_audit


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

    # print('lowest ask {} {} highest bid {} {}'.format(exchange_x.name, exchange_x.lowest_ask, exchange_y.name,
    #                                                   exchange_y.highest_bid))
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

    # print('lowest ask {}  {} highest bid {} {}'.format(exchange_y.name, exchange_y.lowest_ask, exchange_x.name,
    #                                                    exchange_x.highest_bid))
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
    except KeyError as e:
        raise CompareError('Error retrieving volume/price data from exchange object: {}'.format(e))


    trade_valid_sell, price_sell, volume_sell = exchange_sell.trade_validity(price=price_sell, volume=volume)
    trade_valid_buy, price_buy, volume_buy = exchange_buy.trade_validity(price=price_buy, volume=volume)
    if not trade_valid_buy or not trade_valid_sell:
        return Decimal('0')

    # Example
    # lowest ask: we can get 4 BTC (volume) at 99 ETH (price) per BTC
    # highest bid: but we can only sell 3 BTC (volume) at 100 ETH (price) per BTC
    if exchange_sell.highest_bid['volume'] < exchange_buy.lowest_ask['volume']:
        volume = exchange_sell.highest_bid['volume']

    # 3 ETH at 0.1 BTC * 8000 GBP = 2400 GBP > 100 GBP => 3 * (100 / 2400) is the volume
    if volume * price_buy * fiat_rate > FIAT_REPLENISH_AMOUNT:
        volume = FIAT_REPLENISH_AMOUNT / fiat_rate * volume

    try:

        fee = exchange_sell.fee * volume * price_sell + exchange_buy.fee * volume * price_buy
    except:
        raise Exception(type(volume), type(price_sell), type(price_buy), type(exchange_buy.fee),
                        type(exchange_sell.fee))

    profit = ((price_sell - price_buy) * volume - fee) * fiat_rate
    # except Exception as e:
    #     raise Exception(e)

    return profit


# randomly select the names of two exchanges and then check if the trade pair exists in both exchanges
# if the trade pair is not in both exchanges, repeat until we have a pair, up to 10 times
# TODO construct the cross sections of trade pairs and exchanges and randomly select from it instead
def exchange_selection(cur_x, cur_y, markets, jobqueue_id):
    trade_pair = '{}-{}'.format(cur_x, cur_y)
    potential_exchanges = []
    apis_trade_pair_valid = []

    for exchange in markets:
        if trade_pair in markets[exchange] and exchange in EXCHANGES:
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
        imported_exchanges.append(dynamically_import_exchange(exchange)(jobqueue_id))

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
        setup_environment()

    if args.setuponly:
        setup_environment()
        exit()

    markets = load_currency_pairs()

    output = compare(args.curr_x, args.curr_y, markets, args.jobqueue_id)
    return output


class CompareError(Exception):
    pass


if __name__ == "__main__":  # pragma: nocoverage
    setup()
