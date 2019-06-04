import argparse
import logging
from app.settings import LOGLEVEL, MASTER_EXCHANGE, DEFAULT_CURRENCY, FIAT_DEFAULT_SYMBOL
from app.lib.setup import get_exchanges
from app.lib.jobqueue import return_value_to_stdout
from app.lib.common import get_replenish_quantity, get_current_fiat_rate
from app.lib.db import get_replenish_jobs


def replenish(exchange, currency, jobqueue_id):
    # *exchange* has zero quanity of *currency*
    # we need to replenish the stocks from MASTER_EXCHANGE
    # First, check that there was not a replenish job in the last 5 minutes
    recent_jobs = get_replenish_jobs(exchange, currency)
    if not recent_jobs:
        # TODO make a method to get one exchange
        downstream_jobs = []
        exchanges = get_exchanges(jobqueue_id)
        master_exchange = [e for e in exchanges if e.name == MASTER_EXCHANGE][0]
        child_exchange = [e for e in exchanges if e.name == exchange][0]
        fiat_rate = get_current_fiat_rate(crypto_symbol=currency, fiat_symbol=FIAT_DEFAULT_SYMBOL)
        quantity = get_replenish_quantity(fiat_rate)
        if quantity < child_exchange.get_minimum_deposit_volume(currency):
            quantity = child_exchange.get_minimum_deposit_volume(currency)
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
                # this means we did not have enough of the currency to withdraw and will need to convert some DEFAULT_CURRENCY (ETH) to this currency
                downstream_jobs.append({
                    'job_type': 'CONVERT',
                    'job_args': {
                        'exchange': exchange.name,
                        'currency_from': DEFAULT_CURRENCY,
                        'currency_to': currency,
                        'jobqueue_id': jobqueue_id
                    }
                })
                # we will retry this job in 20 seconds time
                # TODO make job queue executor retry jobss
                result['retry'] = int(20)
            else:
                result['success'] = True

        return_value_to_stdout(result)


def setup():
    parser = argparse.ArgumentParser(description='Process some currencies.')
    parser.add_argument('exchange', type=str, help='Currency to compare')
    parser.add_argument('currency', type=str, help='Currency to compare')
    parser.add_argument('jobqueue_id', type=str, help='Jobqueue Id')
    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)

    output = replenish(args.exchange, args.currency)
    return output


class ReplenishError(Exception):
    pass


if __name__ == "__main__":  # pragma: nocoverage
    setup()
