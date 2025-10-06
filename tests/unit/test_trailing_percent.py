from core.domain.services.strategy import compute_trailing_sl_percent


def test_trailing_percent_long_updates_when_improves():
    new_sl = compute_trailing_sl_percent(
        side="long",
        mfe_price=110.0,
        trailing_percent=1.0,
        last_sl=100.0,
        step_min_pct=0.5,
        tick_size=0.01,
    )
    assert new_sl is not None
    assert new_sl > 100.0


def test_trailing_percent_short_updates_when_improves():
    new_sl = compute_trailing_sl_percent(
        side="short",
        mfe_price=90.0,
        trailing_percent=1.0,
        last_sl=100.0,
        step_min_pct=0.5,
        tick_size=0.01,
    )
    assert new_sl is not None
    assert new_sl < 100.0
