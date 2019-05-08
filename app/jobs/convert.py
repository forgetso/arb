import argparse
import logging
from app.settings import LOGLEVEL, MASTER_EXCHANGE
from app.lib.setup import get_exchanges, load_currency_pairs
from app.lib.jobqueue import return_value_to_stdout
from app.lib.common import get_replenish_quantity
from app.lib.db import store_trade
from app.lib.common import get_number_of_decimal_places
from decimal import Decimal, Context, setcontext

def convert(exchange, currency_from, currency_to, markets):
    # we need to add to the stocks in MASTER_EXCHANGE so that we can replenish other exchanges
    # TODO make a method to get one exchange
    exchanges = get_exchanges()
    master_exchange = [e for e in exchanges if e.name == exchange][0]
    quantity = get_replenish_quantity(currency_to)
    master_exchange.set_trade_pair('{}-{}'.format(currency_to, currency_from), markets)
    allowed_decimal_places = get_number_of_decimal_places(str(master_exchange.min_trade_size))
    decimal_rounding_context = Context(prec=allowed_decimal_places)
    setcontext(decimal_rounding_context)
    quantity = Decimal(quantity).normalize()
    result = {'success': False}

    master_exchange.get_pending_balances()

    # we may already be waiting for a deposit to complete with pending confirmations
    # if so, we will not try to replenish again
    logging.debug(master_exchange.pending_balances)
    if currency_to:
        pending_balance = master_exchange.pending_balances.get(currency_to)
        if pending_balance is None or pending_balance == 0:

            # TODO assuming all pairs in the form XXX-BTC. Should be smarter?

            master_exchange.order_book()
            trade = master_exchange.trade('buy', volume=quantity, price=master_exchange.lowest_ask['price'])
            if trade:

                trade['type'] = 'CONVERT'
                store_trade(trade)
                result['trade'] = trade
                result['success'] = True
                return_value_to_stdout(result)
                # {"success": true,
                #  "trade": {"external_id": "27a63353-4aa0-4f7e-bc90-45d087e2c5e5", "_id": "None", "status": "Closed",
                #            "trade_pair_common": "ADX-BTC", "trade_pair": "BTC-ADX", "trade_type": "buy",
                #            "price": 3.16e-05, "volume": 106.47926, "trades_itemised": [],
                #            "date": "2019-02-20T18:15:49.38", "fees": 8.41e-06, "exchange": "bittrex",
                #            "type": "CONVERT"}}

    return result


def setup():
    parser = argparse.ArgumentParser(description='Convert from one currency to another on a particular exchange')
    parser.add_argument('exchange', type=str, help='Exchange name')
    parser.add_argument('currency_from', type=str, help='Currency to convert from')
    parser.add_argument('currency_to', type=str, help='Currency to convert to')
    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)

    markets = load_currency_pairs()
    output = convert(args.exchange, args.currency_from, args.currency_to, markets)
    return output


class ConvertError(Exception):
    pass


if __name__ == "__main__":  # pragma: nocoverage
    setup()
