from app.tools.combinations import process as find_combinations
from app.settings import EXCHANGES
import itertools
from app.lib.setup import load_currency_pairs
import logging
def process():
    markets = load_currency_pairs()
    exchange_combinations = [x for x in itertools.combinations(EXCHANGES, r=2)]
    trade_pair_combinations = []
    for combo in exchange_combinations:
        trade_pair_combinations.append(find_combinations(combo[0], combo[1], markets))
    seta = trade_pair_combinations[0]
    for setb in trade_pair_combinations[1:]:
        seta = seta.intersection(setb)

    logging.debug(seta)
    return seta

if __name__ == "__main__":  # pragma: nocoverage
    process()
