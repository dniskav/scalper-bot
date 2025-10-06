from core.domain.services.strategy import should_move_to_breakeven


def test_be_not_triggered():
    res = should_move_to_breakeven(
        side="long",
        entry_price=100.0,
        sl_current=98.0,
        risk_per_unit=2.0,
        mfe_price=101.9,
        trigger_rr=1.0,
        offset_ticks=0,
        offset_pct=0.0,
        tick_size=0.01,
    )
    assert res is None


def test_be_trigger_exact_with_offset_pct_and_ticks():
    res = should_move_to_breakeven(
        side="long",
        entry_price=100.0,
        sl_current=98.0,
        risk_per_unit=2.0,
        mfe_price=102.0,  # 1.0R
        trigger_rr=1.0,
        offset_ticks=2,  # +2 ticks
        offset_pct=0.02,  # +0.02%
        tick_size=0.01,
    )
    assert res is not None
    # entry*(1+0.0002) + 2*tick = 100.02 + 0.02 = 100.04
    assert abs(res - 100.04) < 1e-6


def test_be_short_side_improves_only():
    res = should_move_to_breakeven(
        side="short",
        entry_price=100.0,
        sl_current=102.0,
        risk_per_unit=2.0,
        mfe_price=98.0,
        trigger_rr=1.0,
        offset_ticks=0,
        offset_pct=0.0,
        tick_size=0.01,
    )
    assert res is not None
    assert res < 102.0
