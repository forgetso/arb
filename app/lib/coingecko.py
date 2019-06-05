from app.settings import FIAT_DEFAULT_SYMBOL
import requests
import os, json

COINGECKO_META = "/app/coingecko_meta.json"


def get_current_fiat_rates(crypto_symbols, fiat_symbol=None):
    if isinstance(crypto_symbols, str):
        crypto_symbols_set = {crypto_symbols}
    else:
        crypto_symbols_set = crypto_symbols
    if not isinstance(crypto_symbols_set, set):
        raise TypeError(
            'Pass a set of crypto symbols for which to find fiat rates. You passed {}'.format(type(crypto_symbols_set)))
    uri = build_fiat_rates_uri(crypto_symbols, fiat_symbol)
    req = requests.get(uri)
    coingecko_rates_data = req.json()
    rates_data = {}
    meta_data = get_coingecko_meta()
    fiat_symbol_key = get_fiat_symbol(fiat_symbol).upper()
    for crypto_symbol in crypto_symbols_set:
        coingecko_symbol = get_coingecko_id(crypto_symbol.lower(), meta_data)
        rates_data[crypto_symbol] = {
            fiat_symbol_key: coingecko_rates_data.get(coingecko_symbol).get(fiat_symbol_key.lower())
        }
    return rates_data


def get_coingecko_id(symbol, metadata):
    result = None
    for m in metadata:
        if m.get('symbol').lower() == symbol.lower(): \
                result = m.get('id')
    return result


def get_coingecko_meta():
    coingecko_meta_file = ''.join([os.getcwd(), COINGECKO_META])
    if not os.path.isfile(coingecko_meta_file):
        uri = "https://api.coingecko.com/api/v3/coins/list"
        req = requests.get(uri)
        coingecko_meta = json.loads(req.content)
        write_coingecko_meta(coingecko_meta)
        result = coingecko_meta
    else:
        with open(coingecko_meta_file) as data_file:
            result = json.loads(data_file.read())
    return result


def write_coingecko_meta(data):
    markets_location = ''.join([os.getcwd(), COINGECKO_META])
    with open(markets_location, 'w') as outfile:
        json.dump(data, outfile, indent=2)


def build_fiat_rates_uri(crypto_symbols, fiat_symbol):
    ids = []
    meta_data = get_coingecko_meta()
    for crypto_symbol in crypto_symbols:
        idsx = get_coingecko_id(crypto_symbol.lower(), meta_data)
        ids.append(idsx.lower())
    fiat_symbol = get_fiat_symbol(fiat_symbol).lower()
    uri = 'https://api.coingecko.com/api/v3/simple/price?ids={}&vs_currencies={}'.format(','.join(ids), fiat_symbol)
    return uri


def get_fiat_symbol(fiat_symbol):
    if not fiat_symbol:
        fiat_symbol = FIAT_DEFAULT_SYMBOL
    else:
        fiat_symbol = fiat_symbol
    return fiat_symbol


def get_current_fiat_rate(crypto_symbol, fiat_symbol=None):
    rate_json = get_current_fiat_rates(crypto_symbol, fiat_symbol)
    fiat_symbol = get_fiat_symbol(fiat_symbol).lower()
    rate = rate_json.get(crypto_symbol).get(fiat_symbol)
    return rate
