from core.domain.services.strategy import evaluate_strategy


def test_no_signal_with_small_data():
    o = [1, 1]
    h = [1, 1]
    l = [1, 1]
    c = [1, 1]
    sig = evaluate_strategy(o, h, l, c, "5m", 1.5, 0.25, 3, 0.01, 0.08)
    assert sig.side == "none"
