import requests
import app.settings as settings
import time
import hmac
import hashlib
from urllib import parse
import urllib3
import subprocess
import re

url = 'https://api.bittrex.com/api/v1.1/market/buylimit'
data = {'apikey': settings.BITTREX_PUBLIC_KEY,
        'market': 'BTC-ETH',
        'quantity': 0.02810933,
        'rate': 0.0001,
        'nonce': int(time.time() * 1000),
        }

paybytes = parse.urlencode(data)

url = '{}?{}'.format(url, paybytes)



newsign = hmac.new(bytearray(settings.BITTREX_PRIVATE_KEY, 'ascii'), bytearray(url, 'ascii'), hashlib.sha512).hexdigest()


headers = {'apisign': newsign}

http = urllib3.PoolManager()
print(url)
r = http.request('GET', url, headers=headers)

print(r.data)
