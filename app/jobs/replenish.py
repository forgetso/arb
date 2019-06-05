import argparse
import logging
from app.settings import LOGLEVEL, DEFAULT_CURRENCY, FIAT_DEFAULT_SYMBOL
from app.lib.setup import get_master_exchange, get_exchange
from app.lib.jobqueue import return_value_to_stdout
from app.lib.common import get_replenish_quantity
from app.lib.coingecko import get_current_fiat_rate
from app.lib.db import get_replenish_jobs, store_audit


def replenish(exchange, currency, jobqueue_id):
    # *exchange* has zero quanity of *currency*
    # we need to replenish the stocks from MASTER_EXCHANGE
    # First, check that there was not a replenish job in the last 5 minutes
    recent_jobs = get_replenish_jobs(exchange, currency)
    result = {'success': False}
    if not recent_jobs:
        downstream_jobs = []
        master_exchange = get_master_exchange(jobqueue_id)
        child_exchange = get_exchange(exchange)
        fiat_rate = get_current_fiat_rate(crypto_symbol=currency, fiat_symbol=FIAT_DEFAULT_SYMBOL)
        quantity = get_replenish_quantity(fiat_rate)
        minimum_deposit = child_exchange.get_minimum_deposit_volume(currency)

        if quantity < minimum_deposit:
            # TODO kill other replenish job
            raise ValueError(
                'Deposit volume {} {} is too low for {}. Minimum is  {}'.format(quantity, currency, exchange,
                                                                                minimum_deposit))
        to_address = child_exchange.get_address(currency)
        result = {'success': False}

        if not to_address:
            raise ReplenishError('No address to send {} for exchange {}'.format(currency, exchange))

        child_exchange.get_pending_balances()

        # we may already be waiting for a deposit to complete with pending confirmations
        # if so, we will not try to replenish again
        if currency not in child_exchange.pending_balances:
            withdrawal_success, uuid = master_exchange.withdraw(currency.upper(), to_address, quantity)

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
                fee = master_exchange.get_withdrawal_tx_fee(currency, uuid)
                fee_fiat = fiat_rate * fee
                store_audit(withdrawal_tx_fee_audit(fee_fiat, fiat_rate, exchange, currency, uuid))
                result['success'] = True

    else:
        result['success'] = True
    return_value_to_stdout(result)


def withdrawal_tx_fee_audit(fee, fee_fiat, exchange, currency, id):
    return {
        'type': 'txfee',
        'fee': fee,
        'fee_fiat': fee_fiat,
        'exchange': exchange,
        'currency': currency,
        'id': id
    }


def setup():
    parser = argparse.ArgumentParser(description='Process some currencies.')
    parser.add_argument('exchange', type=str, help='Currency to compare')
    parser.add_argument('currency', type=str, help='Currency to compare')
    parser.add_argument('jobqueue_id', type=str, help='Jobqueue Id')
    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)

    output = replenish(args.exchange, args.currency, args.jobqueue_id)
    return output


class ReplenishError(Exception):
    pass


if __name__ == "__main__":  # pragma: nocoverage
    setup()
