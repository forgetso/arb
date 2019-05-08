import logging
from app.settings import LOGLEVEL
import argparse
from app.lib.setup import load_currency_pairs
import pprint

def process(exchange_x, exchange_y, markets):
    if exchange_x not in markets:
        exit('{} not in markets'.format(exchange_x))

    if exchange_y not in markets:
        exit('{} not in markets'.format(exchange_y))


    seta =set(markets[exchange_x].keys())
    setb =set(markets[exchange_y].keys())

    intersection = seta.intersection(setb)
    pprint.pprint(intersection)
    exit()


def setup():
    parser = argparse.ArgumentParser(description='Process some currencies.')
    parser.add_argument('exchange_x', type=str, help='Exchange to compare')
    parser.add_argument('exchange_y', type=str, help='Exchange to compare')

    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s', level=LOGLEVEL)

    markets = load_currency_pairs()
    exchange_x = args.exchange_x
    exchange_y = args.exchange_y

    process(exchange_x, exchange_y, markets)


if __name__ == "__main__":  # pragma: nocoverage
    setup()
