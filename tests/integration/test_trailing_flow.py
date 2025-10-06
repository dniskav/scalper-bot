from core.domain.services.strategy import (
    evaluate_strategy,
    should_move_to_breakeven,
    compute_trailing_sl_percent,
)
from core.domain.services.risk import compute_targets


def test_be_trailing_then_sl_close():
    # Construir serie con tendencia, señal long, avance a 1R (BE), luego mayor avance que activa trailing, y retroceso que cierra por SL trailing
    o, h, l, c = [], [], [], []
    price = 100.0
    ts = 0
    # warmup
    for _ in range(60):
        o.append(price)
        h.append(price * 1.003)
        l.append(price * 0.997)
        price = price * 1.002
        c.append(price)
        ts += 1
    # vela roja fuerte a sobreventa
    o.append(price)
    h.append(price * 1.002)
    l.append(price * 0.96)
    c.append(price * 0.965)
    price = c[-1]
    ts += 1
    # vela verde de salida con cuerpo decente (señal)
    o.append(price)
    h.append(price * 1.05)
    l.append(price * 0.99)
    c.append(price * 1.04)
    ts += 1

    sig = evaluate_strategy(o, h, l, c, "5m", 1.5, 0.25, 3, 0.0, 0.08)
    assert sig.side == "long"
    entry = sig.entry  # type: ignore[assignment]
    sl = sig.sl  # type: ignore[assignment]
    rr = sig.rr
    tp = compute_targets(entry, sl, rr, "long")  # type: ignore[arg-type]
    risk = entry - sl  # R por unidad

    # Avance: nuevas velas marcan MFE por encima de 1R
    mfe = entry
    for _ in range(3):
        o.append(c[-1])
        new_high = max(c[-1] * 1.02, entry + 1.1 * risk)
        h.append(new_high)
        l.append(c[-1] * 0.995)
        c.append(c[-1] * 1.01)
        mfe = max(mfe, new_high)

    # BE
    new_sl = should_move_to_breakeven(
        side="long",
        entry_price=entry,  # type: ignore[arg-type]
        sl_current=sl,  # type: ignore[arg-type]
        risk_per_unit=risk,  # type: ignore[arg-type]
        mfe_price=mfe,
        trigger_rr=1.0,
        offset_ticks=0,
        offset_pct=0.0,
        tick_size=0.01,
    )
    assert new_sl is not None and new_sl >= entry  # BE movido
    sl = new_sl  # type: ignore[assignment]

    # Trailing percent: subir MFE y comprobar nueva mejora de SL
    o.append(c[-1])
    new_high = c[-1] * 1.05
    h.append(new_high)
    l.append(c[-1] * 0.995)
    c.append(c[-1] * 1.02)
    mfe = max(mfe, new_high)
    trail_sl = compute_trailing_sl_percent(
        side="long",
        mfe_price=mfe,
        trailing_percent=1.0,
        last_sl=sl,  # type: ignore[arg-type]
        step_min_pct=0.1,
        tick_size=0.01,
    )
    assert trail_sl is not None and trail_sl > sl  # type: ignore[operator]
    sl = trail_sl  # type: ignore[assignment]

    # Retroceso por debajo del SL trailing -> cierre por SL con ganancia
    px_exit = sl * 0.999
    assert px_exit < sl  # type: ignore[operator]
    pnl = px_exit - entry  # type: ignore[operator]
    assert pnl > 0
