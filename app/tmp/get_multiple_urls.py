import requests
from concurrent.futures import ProcessPoolExecutor as PoolExecutor

urls = [
    "http://www.google.com",
    "http://www.youtube.com",]

def get_it(url):
    try:
        r = requests.get(url)
    except Exception as e:
        print(e)
    return r

with PoolExecutor(max_workers=4) as executor:

    # distribute the 1000 URLs among 4 threads in the pool
    # _ is the body of each page that I'm ignoring right now
    for response in executor.map(get_it, urls):
        print(response.content)