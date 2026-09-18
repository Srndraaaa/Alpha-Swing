from scoring import sma, ema, regime, mansfield, atr

def test_sma_needs_full_period():
    assert sma([1.0, 2.0], 5) is None
    assert sma([1.0, 2.0, 3.0, 4.0], 4) == 2.5

def test_ema_flat_series_equals_value():
    assert ema([10.0] * 30, 20) == 10.0

def test_regime_matrix():
    assert regime(110.0, 105.0, 100.0, 15.0) == "RISK-ON"
    assert regime(103.0, 105.0, 100.0, 20.0) == "NEUTRAL"
    assert regime(99.0, 105.0, 100.0, 15.0) == "RISK-OFF"
    assert regime(110.0, 105.0, 100.0, 25.0) == "RISK-OFF"

def test_mansfield_needs_60_bars():
    assert mansfield([1.0] * 59, [1.0] * 59) is None

def test_mansfield_flat_ratio_is_zero():
    assert mansfield([100.0] * 70, [400.0] * 70) == 0.0
from scoring import (pillar_rs, vcp, pillar_fund, pillar_flow, apply_blackout,
                     categorize, levels, rr, position_size, filter_rows)

def test_atr_flat_series_equals_range():
    h = [101.0] * 20
    l = [99.0] * 20
    c = [100.0] * 20
    assert atr(h, l, c) == 2.0

def _vcp_data():
    h = [110.0] * 30 + [105.0] * 30 + [102.0] * 30
    l = [95.0] * 30 + [98.0] * 30 + [99.0] * 30
    v = [1000.0] * 89 + [400.0]
    w = [100.0 + i for i in range(31)]
    return h, l, v, w

def test_pillar_rs_bands():
    assert pillar_rs(92.0) == (15, "")
    assert pillar_rs(87.0) == (12, "")
    assert pillar_rs(82.0) == (10, "")
    assert pillar_rs(77.0) == (8, "")
    assert pillar_rs(72.0) == (5, "")
    assert pillar_rs(50.0) == (0, "")
    assert pillar_rs(None) == (0, "DATA_TIPIS")

def test_vcp_full_scores_25_ready():
    assert vcp(*_vcp_data()) == (25, "Ready")

def test_vcp_no_contraction_scores_0():
    h = [100.0] * 90
    l = [99.0] * 90
    v = [1000.0] * 90
    w = [100.0 + i for i in range(31)]
    s, st = vcp(h, l, v, w)
    assert st == "Not Ready" and s < 25

def test_fund_and_flow_missing_data_flagged():
    assert pillar_fund("Buy", 20.0, 1.5) == (25, "")
    assert pillar_fund(None, None, None)[1] == "N/A"
    assert pillar_flow(0.3, True, True, True) == (20, "")
    assert pillar_flow(None, False, True, False) == (5, "N/A-OPTIONS")

def test_blackout_and_category():
    assert apply_blackout(90, 5) == (63, True)
    assert apply_blackout(90, 8) == (90, False)
    assert apply_blackout(90, None) == (90, False)
    assert categorize(92, False) == "ULTRA"
    assert categorize(87, False) == "HIGH"
    assert categorize(70, False) == "MODERATE"
    assert categorize(95, True) == "EARNINGS BLACKOUT"

def test_levels_rr_sizing():
    sl, tp, buy = levels(100.0, 2.0)
    assert (sl, tp, buy) == (97.0, 106.0, 99.0)
    assert rr(100.0, sl, tp) == 2.0
    assert rr(100.0, 100.0, 106.0) is None
    assert position_size(10000.0, 1.0, 100.0, 97.0) == 33
    assert position_size(10000.0, 1.0, 100.0, 100.0) == 0
    assert levels(100.0, None) == (None, None, None)

def test_filter_rows_stage5():
    rows = [
        {"ticker": "AAA", "name": "Alpha", "sector": "Tech", "score": 92,
         "rs": 91.0, "vcp": "Ready", "blackout": False},
        {"ticker": "BBB", "name": "Beta", "sector": "Bank", "score": 80,
         "rs": 70.0, "vcp": "Not Ready", "blackout": False},
    ]
    assert [r["ticker"] for r in filter_rows(rows, "ULTRA", "")] == ["AAA"]
    assert [r["ticker"] for r in filter_rows(rows, "VCP", "")] == ["AAA"]
    assert [r["ticker"] for r in filter_rows(rows, "RS", "")] == ["AAA"]
    assert [r["ticker"] for r in filter_rows(rows, "ALL", "beta")] == ["BBB"]
    assert [r["ticker"] for r in filter_rows(rows, "ALL", "")] == ["AAA", "BBB"]
