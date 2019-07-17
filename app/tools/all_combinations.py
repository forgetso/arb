from app.tools.combinations import process as find_combinations
from app.settings import EXCHANGES
import itertools
from app.lib.setup import load_currency_pairs
import logging


def process():
    trade_pair_combinations = get_combinations()
    seta = trade_pair_combinations[0]
    for setb in trade_pair_combinations[1:]:
        seta = seta.intersection(setb)

    # logging.debug(seta)
    return seta


def get_combinations():
    markets = load_currency_pairs()
    exchange_combinations = [x for x in itertools.combinations(EXCHANGES, r=2)]
    trade_pair_combinations = []
    for combo in exchange_combinations:
        trade_pair_combinations.append(find_combinations(combo[0], combo[1], markets))
    return trade_pair_combinations


def trade_paths():
    trade_pair_combinations = get_combinations()
    trade_paths = []
    for combo in trade_pair_combinations:
        pair_a = combo[0].split('-')
        pair_b = combo[1].split('-')
        join = [x for x in pair_a if x in pair_b]
        if join:
            trade_paths.append([pair_a, pair_b])

    print(trade_paths)


if __name__ == "__main__":  # pragma: nocoverage
    process()
