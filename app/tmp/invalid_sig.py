from bittrex.bittrex import Bittrex, API_V2_0
import app.settings as s
my_bittrex = Bittrex(s.BITTREX_PUBLIC_KEY, s.BITTREX_PUBLIC_KEY, api_version=API_V2_0)
result = my_bittrex.trade_buy('BTC-ADX', 'LIMIT', 50.0, 0.001, 'GOOD_TIL_CANCELLED', 'NONE', 0)
print(result)