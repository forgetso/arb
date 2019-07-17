from app.jobs.multi import bellman_ford, construct_rate_graph, match_order_book
from testdata.wraps.wrap_exchange1 import exchange1
from testdata.wraps.wrap_exchange2 import exchange2
from testdata.apis.exchange1_api import ORDER_BOOK
from tests.jobs.test_compare import JOBQUEUE_ID
from testdata.markets import MARKETS
from decimal import Decimal


class TestClass(object):
    def setup(self):
        self.exchanges = []
        self.exchanges.append(exchange1(jobqueue_id=JOBQUEUE_ID))
        self.exchanges.append(exchange1(jobqueue_id=JOBQUEUE_ID))
        self.exchanges.append(exchange1(jobqueue_id=JOBQUEUE_ID))
        trade_pairs = ['REP-ETH', 'REP-BTC', 'ETH-BTC']
        currencies = []
        for count, trade_pair in enumerate(trade_pairs):
            self.exchanges[count].set_trade_pair(trade_pair, MARKETS)
            currencies.append(self.exchanges[count].base_currency)
            currencies.append(self.exchanges[count].quote_currency)
        self.currencies = sorted(list(set(currencies)))
        assert self.currencies == ['BTC', 'ETH', 'REP']
        for exchange in self.exchanges:
            exchange.order_book()
            assert exchange.lowest_ask['price'] > exchange.highest_bid['price']

    # def test_construct_rate_graph(self):
    #     self.setup()
    #
    #     graph = construct_rate_graph(self.currencies, self.exchanges)
    #
    #     # correct output should be a list of rates based on the row currency
    #     # row currency is determined by the order of self.currencies
    #     # therefore row[0] = BTC, rates should be set to 1 BTC: 0.000X OTHER
    #     correct_output = [
    #         # so row 0 is exchange rate of BTC:BTC, BTC:ETH, BTC:REP
    #         [float('inf'), Decimal('10'), Decimal('1') / Decimal(ORDER_BOOK['REP-BTC']['result']['sell'][0]['Rate'])],
    #         # so row 1 is exchange rate of ETH:BTC, ETH:ETH, ETH:REP
    #         [Decimal('0.09'), float('inf'), Decimal('1') / Decimal('0.05')],
    #         # so row 2 is exchange rate of REP:BTC, REP:ETH, REP:REP
    #         [Decimal('0.0020000'), Decimal('0.040000'), float('inf')]
    #     ]
    #     print(correct_output)
    #     assert graph[0] == correct_output[0]
    #     assert graph[1] == correct_output[1]
    #     assert graph[2] == correct_output[2]

    def test_match_order_book(self):
        self.setup()
        assert self.exchanges[2].trade_pair_common == 'ETH-BTC'
        assert len(self.exchanges[2].bids) == 3
        # this is selling BASE for QUOTE (bids)
        bought, _ = match_order_book(exchange=self.exchanges[2],
                                     to_sell=Decimal('2.005'),
                                     buy_type='bids',
                                     sell_symbol=self.exchanges[2].base_currency)
        assert bought == Decimal('0.177442')
        # this is selling QUOTE for BASE (asks)
        bought, _ = match_order_book(exchange=self.exchanges[2],
                                     to_sell=Decimal('0.278'),
                                     buy_type='asks',
                                     sell_symbol=self.exchanges[2].quote_currency)
        assert bought == Decimal('2.7090909')
        bought, _ = match_order_book(exchange=self.exchanges[2],
                                     to_sell=Decimal('0.170'),
                                     buy_type='asks',
                                     sell_symbol=self.exchanges[2].quote_currency)
        assert bought == Decimal('1.7')

        # now use some real LTC ETH data. Here 42 LTC are selling at rate 0.42 ETH
        self.exchanges[2].asks = [{'price': Decimal('0.425564'), 'volume': Decimal('42.806')}]
        self.exchanges[2].base_currency = 'LTC'
        self.exchanges[2].quote_currency = 'ETH'
        # we want to sell 2.9955 ETH
        to_sell = Decimal('2.9955')
        print(self.exchanges[2].asks)
        bought, transactions = match_order_book(exchange=self.exchanges[2],
                                     to_sell=to_sell,
                                     buy_type='asks',
                                     sell_symbol=self.exchanges[2].quote_currency)
        # we can buy (to_sell / price * volume) * volume
        assert bought == Decimal('7.0388941')

        computed_sell = sum([tx['buy'] * tx['price'] for tx in transactions])

        # want to be less than 1% out
        assert computed_sell / to_sell < 1.001
