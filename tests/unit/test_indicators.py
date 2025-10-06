from core.domain.services.indicators import ema, rsi, adx


def test_ema_basic():
    vals = [1, 2, 3, 4, 5]
    out = ema(vals, 3)
    assert len(out) == len(vals)
    assert out[-1] > out[0]


def test_rsi_bounds():
    vals = [i for i in range(1, 50)]
    r = rsi(vals, 3)
    assert all(0 <= x <= 100 for x in r)


def test_adx_shape():
    h = [5, 6, 7, 8, 9, 10]
    l = [1, 2, 3, 4, 5, 6]
    c = [3, 4, 5, 6, 7, 8]
    a = adx(h, l, c, 5)
    assert len(a) == len(c)
