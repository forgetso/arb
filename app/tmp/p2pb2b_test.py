from app.wraps.wrap_p2pb2b import p2pb2b
from app.lib.setup import load_currency_pairs
from app.lib.db import remove_api_method_locks

remove_api_method_locks()
client = p2pb2b()
markets = load_currency_pairs()
client.set_trade_pair('ETH-BTC', markets)
client.get_balances()
print('1')
client.get_balances()
print('2')
client.get_balances()
print('3')
client.get_balances()
print('4')
client.get_balances()
print('5')
