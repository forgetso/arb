import argparse
import logging
from app.settings import LOGLEVEL, DEFAULT_CURRENCY, FIAT_DEFAULT_SYMBOL
from app.lib.setup import get_master_exchange, get_exchange
from app.lib.jobqueue import return_value_to_stdout
from app.lib.common import get_replenish_quantity
from app.lib.coingecko import get_current_fiat_rate
from app.lib.db import get_replenish_jobs, store_audit, exchange_lock


def replenish(exchange, currency, jobqueue_id):
    # *exchange* has zero quanity of *currency*
    # we need to replenish the stocks from MASTER_EXCHANGE
    # First, check that there was not a replenish job in the last 5 minutes
    exchange_lock(exchange, jobqueue_id, 'REPLENISH', lock=True)
    recent_jobs = get_replenish_jobs(exchange, currency)
    result = {'success': False}
    pending_balances_not_implemented = True
    downstream_jobs = []

    if not recent_jobs:

        master_exchange = get_master_exchange(jobqueue_id)
        child_exchange = get_exchange(exchange, jobqueue_id)
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

        try:
            # some exchanges do not provide the functionality to check for pending balances so we have to assume the crypto is sent
            child_exchange.get_pending_balances()
        except NotImplementedError:
            pending_balances_not_implemented = True
            pass

        child_exchange.get_balances()

        # we may already be waiting for a deposit to complete with pending confirmations
        # if so, we will not try to replenish again
        if currency in child_exchange.pending_balances:
            pass
        elif currency not in child_exchange.pending_balances or pending_balances_not_implemented:
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
                # TODO make job queue executor retry jobs
                result['retry'] = int(20)
            else:
                result['success'] = True
                audit_id = store_audit(withdrawal_tx_fee_audit(0, fiat_rate, 0, exchange, currency, uuid))
                downstream_jobs.append(withdrawal_fee_job(master_exchange.name, currency, uuid, audit_id))
    else:
        result['success'] = True
    if downstream_jobs:
        result['downstream_jobs'] = downstream_jobs
    exchange_lock(exchange, jobqueue_id, 'REPLENISH', lock=False)
    return_value_to_stdout(result)


def withdrawal_fee_job(exchange_name, currency, id, audit_id):
    return {
        'job_type': 'WITHDRAWAL_FEE',
        'job_args': {
            'exchange': exchange_name,
            'currency': currency,
            'withdrawal_id': id,
            'audit_id': str(audit_id)
        }
    }


def withdrawal_tx_fee_audit(fee, fiat_rate, fee_fiat, exchange, currency, id):
    return {
        'type': 'txfee',
        'fee': fee,
        'fiat_rate': fiat_rate,
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
