# this would usually be loaded from a json file
MARKETS = {'exchange1':
    {"ETH-BTC": {
        "name": "ETH-BTC",
        "trading_code": "BTC-ETH",
        "base_currency": "ETH",
        "quote_currency": "BTC",
        "min_trade_size": 0.00740642,
        "decimal_places": 8,
        "min_trade_size_currency": "ETH",
        "fee": 0.001
    }, "ETH-ADX": {
        "name": "ETH-ADX",
        "trading_code": "ETH-ADX",
        "base_currency": "ETH",
        "quote_currency": "ADX",
        "min_trade_size": 0.00740642,
        "decimal_places": 8,
        "min_trade_size_currency": "ETH",
        "fee": 0.001
    }, "REP-ETH": {
        "name": "REP-ETH",
        "trading_code": "ETH-REP",
        "base_currency": "REP",
        "quote_currency": "ETH",
        "min_trade_size": 0.0475009,
        "decimal_places": 7,
        "min_trade_size_currency": "REP",
        "fee": 0.0025
    }, "REP-BTC": {
        "name": "REP-BTC",
        "trading_code": "REP-BTC",
        "base_currency": "REP",
        "quote_currency": "BTC",
        "decimal_places": 7,
        "min_trade_size": 0.001,
        "min_trade_size_currency": "REP",
        "fee": 0.002
    },
    },
    'exchange2':
        {"ETH-BTC": {
            "name": "ETH-BTC",
            "trading_code": "ETHBTC",
            "base_currency": "ETH",
            "quote_currency": "BTC",
            "decimal_places": 3,
            "min_trade_size": 0.001,
            "min_trade_size_currency": "ETH",
            "min_notional": 0.001,
            "taker_fee": 0.001,
            "maker_fee": 0.001,
            "fee": 0.001
        },
            "ETH-ADX": {
                "name": "ETH-ADX",
                "trading_code": "ETHADX",
                "base_currency": "ETH",
                "quote_currency": "ADX",
                "decimal_places": 3,
                "min_trade_size": 0.001,
                "min_trade_size_currency": "ETH",
                "min_notional": 0.001,
                "taker_fee": 0.001,
                "maker_fee": 0.001,
                "fee": 0.001
            },
            "REP-BTC": {
                "name": "REP-BTC",
                "trading_code": "REP-BTC",
                "base_currency": "REP",
                "quote_currency": "BTC",
                "decimal_places": 7,
                "min_trade_size": 0.001,
                "min_trade_size_currency": "REP",
                "fee": 0.002
            },
        },

    # this exchange will be ignored as it doesn't exist in our allowed list of exchanges
    'exchange3':
        {"ETH-BTC": {
            "name": "ETH-BTC",
            "trading_code": "ETHBTC",
            "base_currency": "ETH",
            "quote_currency": "BTC",
            "decimal_places": 3,
            "min_trade_size": 0.001,
            "min_trade_size_currency": "ETH",
            "min_notional": 0.001,
            "taker_fee": 0.001,
            "maker_fee": 0.001,
            "fee": 0.001
        }},
    'p2pb2b': {
        "ETH-BTC": {
            "name": "ETH-BTC",
            "trading_code": "ETH_BTC",
            "base_currency": "ETH",
            "quote_currency": "BTC",
            "decimal_places": 3,
            "decimal_places_base": 6,
            "min_trade_size": 0.001,
            "min_trade_size_currency": "ETH",
            "maker_fee": 0.002,
            "taker_fee": 0.002,
            "fee": 0.002
        }}

}
