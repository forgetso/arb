from app.wraps.wrap_p2pb2b import p2pb2b
from app.lib.setup import load_currency_pairs
from app.lib.db import remove_api_method_locks

remove_api_method_locks()
client = p2pb2b('5ce9c1264d306651243edc3f')
# markets = load_currency_pairs()
# client.set_trade_pair('ETH-BTC', markets)
# client.get_balances()
# print(client.balances['BTC'])
client.get_order(order_id='123456')