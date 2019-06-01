from app.lib.setup import load_currency_pairs


def test_markets():
    markets = load_currency_pairs()
    for exchange in markets:
        for trade_pair in markets[exchange]:
            # "SC-USD": {
            #     "name": "SC-USD",
            #     "trading_code": "USD-SC",
            #     "base_currency": "SC",
            #     "quote_currency": "USD",
            #     "min_trade_size": 1000.0,
            #     "decimal_places": 1,
            #     "min_trade_size_currency": "SC",
            #     "fee": 0.0025
            # },
            assert 'name' in markets[exchange][trade_pair]
            assert 'trading_code' in markets[exchange][trade_pair]
            assert 'base_currency' in markets[exchange][trade_pair]
            assert 'quote_currency' in markets[exchange][trade_pair]
            assert 'min_trade_size' in markets[exchange][trade_pair]
            assert 'decimal_places' in markets[exchange][trade_pair]
            assert 'min_trade_size_currency' in markets[exchange][trade_pair]
            assert 'fee' in markets[exchange][trade_pair]
