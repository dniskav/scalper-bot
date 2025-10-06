from core.domain.services.strategy import compute_trailing_sl_atr


def test_trailing_atr_long():
    new_sl = compute_trailing_sl_atr(
        side="long",
        current_price=105.0,
        atr_value=1.0,
        atr_mult=2.0,
        last_sl=100.0,
        step_min_pct=0.5,
        tick_size=0.01,
    )
    assert new_sl is not None
    assert new_sl > 100.0


def test_trailing_atr_short():
    new_sl = compute_trailing_sl_atr(
        side="short",
        current_price=95.0,
        atr_value=1.0,
        atr_mult=2.0,
        last_sl=100.0,
        step_min_pct=0.5,
        tick_size=0.01,
    )
    assert new_sl is not None
    assert new_sl < 100.0
