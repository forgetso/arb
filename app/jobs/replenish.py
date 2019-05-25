import argparse
import logging
from app.settings import LOGLEVEL, MASTER_EXCHANGE, BASE_CURRENCY, FIAT_DEFAULT_SYMBOL
from app.lib.setup import get_exchanges
from app.lib.jobqueue import return_value_to_stdout
from app.lib.common import get_replenish_quantity, get_current_fiat_rate


def replenish(exchange, currency):
    # *exchange* has zero quanity of *currency*
    # we need to replenish the stocks from MASTER_EXCHANGE
    # TODO make a method to get one exchange
    downstream_jobs = []
    exchanges = get_exchanges()
    master_exchange = [e for e in exchanges if e.name == MASTER_EXCHANGE][0]
    child_exchange = [e for e in exchanges if e.name == exchange][0]
    fiat_rate = get_current_fiat_rate(crypto_symbol=currency, fiat_symbol=FIAT_DEFAULT_SYMBOL)
    quantity = get_replenish_quantity(fiat_rate)
    to_address = child_exchange.get_address(currency)
    result = {'success': False}

    if not to_address:
        raise ReplenishError('No address to send {} for exchange {}'.format(currency, exchange))

    child_exchange.get_pending_balances()

    # we may already be waiting for a deposit to complete with pending confirmations
    # if so, we will not try to replenish again
    if currency not in child_exchange.pending_balances:
        withdrawal_success = master_exchange.withdraw(currency.upper(), to_address, quantity)
        if not withdrawal_success:
            # this means we did not have enough of the currency to withdraw and will need to convert some BTC to this currency
            downstream_jobs.append({
                'job_type': 'CONVERT',
                'job_args': {
                    'exchange': exchange.name,
                    'currency_from': BASE_CURRENCY,
                    'currency_to': currency
                }
            })
            # we will retry this job in 20 seconds time
            result['retry'] = int(20)
        else:
            result['success'] = True

    return_value_to_stdout(result)


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
