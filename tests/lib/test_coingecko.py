from app.lib.coingecko import build_fiat_rates_uri


def test_build_fiat_rates_uri():
    metadata = [
        {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin"
        },
        {
            "id": "ethereum",
            "symbol": "eth",
            "name": "Ethereum"
        },
        {
            "id": "adex",
            "symbol": "adx",
            "name": "AdEx"
        }

    ]

    uri = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,adex&vs_currencies=gbp'

    result = build_fiat_rates_uri(['btc', 'eth', 'adx'], 'gbp', metadata)
    assert type(result) is str
    assert result == uri

    result = build_fiat_rates_uri(['BTC', 'ETH', 'ADX'], 'GBP', metadata)
    assert result == uri


def test_get_current_fiat_rate(monkeypatch):
    def substitute_func(uri):
        return {"adex": {"gbp": 0.121857}, "bitcoin": {"gbp": 6054.32}, "ethereum": {"gbp": 181.71}}

    import app.lib.coingecko as coingecko
    monkeypatch.setattr(coingecko, 'api_request', substitute_func)
    rate = coingecko.get_current_fiat_rate('ETH', 'GBP')
    assert type(rate) is float
