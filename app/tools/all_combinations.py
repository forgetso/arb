from app.tools.combinations import process as find_combinations
from app.settings import EXCHANGES
import itertools
from app.lib.setup import load_currency_pairs
import logging


def process():
    seta = get_intersections()

    # logging.debug(seta)
    return seta


def get_intersections():
    trade_pair_combinations = get_combinations()
    seta = trade_pair_combinations[0]
    for setb in trade_pair_combinations[1:]:
        seta = seta.intersection(setb)
    return seta


def get_combinations():
    markets = load_currency_pairs()
    exchange_combinations = [x for x in itertools.combinations(EXCHANGES, r=2)]
    trade_pair_combinations = []
    for combo in exchange_combinations:
        trade_pair_combinations.append(find_combinations(combo[0], combo[1], markets))
    return trade_pair_combinations


def get_combinations_split():
    trade_pair_combinations = get_intersections()

    split_combos = []
    for trade_pair in trade_pair_combinations:
        pair = trade_pair.split('-')
        split_combos.append(pair)
    return split_combos


def trade_paths():
    trade_paths = []
    split_combos = get_combinations_split()
    joins = []
    for trade_pair_x in split_combos:
        for trade_pair_y in split_combos:
            join = [x for x in trade_pair_x if x in trade_pair_y and trade_pair_x != trade_pair_y]
            if join:
                joins.append(frozenset(trade_pair_x))
                joins.append(frozenset(trade_pair_y))

    import pprint
    pprint.pprint(set(joins))


if __name__ == "__main__":  # pragma: nocoverage
    process()
