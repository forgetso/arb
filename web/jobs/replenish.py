import argparse
import logging
from web.settings import LOGLEVEL, MASTER_EXCHANGE, FIAT_REPLENISH_AMOUNT, FIAT_DEFAULT_SYMBOL
from web.lib.setup import get_exchanges, get_current_fiat_rate
from web.lib.jobqueue import return_value_to_stdout


def replenish(exchange, currency):
    # this exchange has none of this currency
    # we need to replenish the stocks from ... TODO choose a master exchange? Bittrex?
    # TODO make a method to get one exchange
    exchanges = get_exchanges()
    master_exchange = [e for e in exchanges if e.name == MASTER_EXCHANGE][0]
    child_exchange = [e for e in exchanges if e.name == exchange][0]
    quantity = get_replenish_quantity(currency)
    to_address = child_exchange.get_address(currency)

    if not to_address:
        raise ReplenishError('No address to send {} for exchange {}'.format(currency, exchange))

    child_exchange.get_pending_balances()

    # we may already be waiting for a deposit to complete with pending confirmations
    # if so, we will not try to replenish again
    if currency not in child_exchange.pending_balances:
        master_exchange.withdraw(currency.upper(), to_address, quantity)

    return_value_to_stdout({'success': True})


def get_replenish_quantity(currency):
    fiat_rate = get_current_fiat_rate(fiat_symbol=FIAT_DEFAULT_SYMBOL, crypto_symbol=currency)
    try:
        quantity = FIAT_REPLENISH_AMOUNT / fiat_rate
    except Exception as e:
        raise ReplenishError('Error getting replenish quantity {}'.format(e))

    return quantity


def setup():
    parser = argparse.ArgumentParser(description='Process some currencies.')
    parser.add_argument('exchange', type=str, help='Currency to compare')
    parser.add_argument('currency', type=str, help='Currency to compare')
    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)

    output = replenish(args.exchange, args.currency)
    return output


class ReplenishError(Exception):
    pass


if __name__ == "__main__":  # pragma: nocoverage
    setup()
