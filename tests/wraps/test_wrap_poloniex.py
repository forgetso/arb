from app.wraps.wrap_poloniex import poloniex


def test_can_initialise_class():
    initialised = poloniex(jobqueue_id='x')
    assert (isinstance(initialised, poloniex))
