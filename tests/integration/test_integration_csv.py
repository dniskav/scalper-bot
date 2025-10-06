import csv
from core.domain.services.strategy import evaluate_strategy
from core.domain.services.risk import compute_targets


def load_csv(path: str):
    o, h, l, c = [], [], [], []
    with open(path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            # ts,open,high,low,close,volume
            o.append(float(row[1]))
            h.append(float(row[2]))
            l.append(float(row[3]))
            c.append(float(row[4]))
    return o, h, l, c


def test_integration_signal_from_csv(tmp_path):
    csv_path = tmp_path / "candles_5m_sample.csv"
    csv_path.write_text(
        """# ts,open,high,low,close,volume
1725504000000,100.0,101.0,99.5,100.5,120
1725504300000,100.5,101.5,100.4,101.2,110
1725504600000,101.2,102.5,101.0,102.0,115
1725504900000,102.0,102.2,101.1,101.2,130
1725505200000,101.2,101.4,100.0,100.2,140
1725505500000,100.2,100.3,98.9,99.2,150
1725505800000,99.2,99.4,97.8,98.4,160
1725506100000,98.4,98.6,97.5,97.8,170
1725506400000,97.8,98.2,96.9,97.2,180
1725506700000,97.2,98.0,96.8,97.9,175
1725507000000,97.9,99.0,97.8,98.8,165
1725507300000,98.8,100.0,98.6,99.5,160
1725507600000,99.5,100.2,99.4,100.1,150
1725507900000,100.1,101.0,100.0,100.9,145
1725508200000,100.9,102.0,100.8,101.8,140
1725508500000,101.8,103.0,101.7,102.6,135
1725508800000,102.6,103.8,102.5,103.2,130
1725509100000,103.2,104.0,102.9,103.7,125
1725509400000,103.7,104.5,103.5,104.2,120
1725509700000,104.2,104.8,103.9,104.6,118
1725510000000,104.6,105.5,104.3,105.2,115
"""
    )

    o, h, l, c = load_csv(str(csv_path))
    sig = evaluate_strategy(o, h, l, c, "5m", 1.5, 0.25, 3, 0.02, 0.08)
    assert sig.side in ("none", "long", "short")


def test_integration_constructed_long_and_short(tmp_path):
    # Construir series que potencialmente produzcan señales long/short y validar TP de compute_targets
    def write_rows(rows, name):
        p = tmp_path / name
        p.write_text(
            "# ts,open,high,low,close,volume\n"
            + "\n".join(
                f"{r[0]},{r[1]:.4f},{r[2]:.4f},{r[3]:.4f},{r[4]:.4f},{r[5]}"
                for r in rows
            )
        )
        return p

    # Long case
    rows = []
    ts = 1725600000000
    price = 100.0
    for i in range(60):
        o = price
        h = price * 1.003
        l = price * 0.997
        c = price * 1.002
        rows.append((ts, o, h, l, c, 100 + i))
        ts += 300000
        price = c
    o = price
    h = price * 1.001
    l = price * 0.96
    c = price * 0.965
    rows.append((ts, o, h, l, c, 999))
    ts += 300000
    price = c
    o = price
    h = price * 1.06
    l = price * 0.99
    c = price * 1.05
    rows.append((ts, o, h, l, c, 999))
    p_long = write_rows(rows, "long.csv")
    oL, hL, lL, cL = load_csv(str(p_long))
    sigL = evaluate_strategy(oL, hL, lL, cL, "5m", 1.5, 0.25, 3, 0.02, 0.08)
    assert sigL.side in ("long", "none")
    if sigL.side == "long":
        tp = compute_targets(sigL.entry, sigL.sl, sigL.rr, "long")  # type: ignore[arg-type]
        assert tp > sigL.entry  # type: ignore[operator]

    # Short case
    rows = []
    ts = 1725700000000
    price = 200.0
    for i in range(60):
        o = price
        h = price * 1.003
        l = price * 0.997
        c = price * 0.998
        rows.append((ts, o, h, l, c, 100 + i))
        ts += 300000
        price = c
    o = price
    h = price * 1.06
    l = price * 0.99
    c = price * 1.05
    rows.append((ts, o, h, l, c, 999))
    ts += 300000
    price = c
    o = price
    h = price * 1.01
    l = price * 0.94
    c = price * 0.95
    rows.append((ts, o, h, l, c, 999))
    p_short = write_rows(rows, "short.csv")
    oS, hS, lS, cS = load_csv(str(p_short))
    sigS = evaluate_strategy(oS, hS, lS, cS, "5m", 1.5, 0.25, 3, 0.02, 0.08)
    assert sigS.side in ("short", "none")
    if sigS.side == "short":
        tp = compute_targets(sigS.entry, sigS.sl, sigS.rr, "short")  # type: ignore[arg-type]
        assert tp < sigS.entry  # type: ignore[operator]
