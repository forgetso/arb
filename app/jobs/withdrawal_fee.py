import argparse
import logging
from app.settings import LOGLEVEL, MASTER_EXCHANGE
from app.lib.setup import get_exchange, get_master_exchange
from app.lib.jobqueue import return_value_to_stdout
from app.lib.db import update_withdrawal_fee
from bson import ObjectId


def withdrawal_fee(exchange_name, currency, withdrawal_id, audit_id, jobqueue_id):
    result = {'success': False}
    try:
        if exchange_name == MASTER_EXCHANGE:
            exchange = get_master_exchange(jobqueue_id=jobqueue_id)
        else:
            exchange = get_exchange(exchange_name, jobqueue_id=jobqueue_id)
        fee = exchange.get_withdrawal_tx_fee(currency, withdrawal_id)
        update_withdrawal_fee(ObjectId(audit_id), fee)
        result['success'] = True

    except Exception as e:
        raise WithdrawalFeeError('Problem getting withdrawal fee from Master Exchange: {}'.format(e))

    return_value_to_stdout(result)


def setup():
    parser = argparse.ArgumentParser(description='Get the withdrawal fee for a withdrawal and update the database')
    parser.add_argument('exchange', type=str, help='Exchange name')
    parser.add_argument('currency', type=str, help='Currency to compare')
    parser.add_argument('withdrawal_id', type=str, help='ID of withdrawal on 3rd party exchange')
    parser.add_argument('audit_id', type=str, help='ID of audit record to be updated')
    parser.add_argument('jobqueue_id', type=str, help='Jobqueue Id')
    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)

    output = withdrawal_fee(args.exchange, args.currency, args.withdrawal_id, args.audit_id, args.jobqueue_id)
    return output


class WithdrawalFeeError(Exception):
    pass


if __name__ == "__main__":  # pragma: nocoverage
    setup()
