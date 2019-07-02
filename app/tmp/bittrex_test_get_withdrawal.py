from app.wraps.wrap_bittrex import bittrex

b = bittrex('x')
fee = b.get_withdrawal_tx_fee('BTC', '657ea9ca-0daf-41d1-b90e-d263d055f774')
print(fee)
