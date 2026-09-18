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
