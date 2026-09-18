from finnhub import Bucket, Finnhub, MOCK

def test_bucket_blocks_third_call_with_fake_clock():
    t = [0.0]
    b = Bucket(per_min=2, now=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s))
    b.acquire()
    b.acquire()
    b.acquire()
    assert t[0] == 30.0

def test_mock_quote_is_deterministic():
    f = Finnhub("MOCK")
    assert f.get("/quote", {"symbol": "AAPL"}) == f.get("/quote", {"symbol": "AAPL"})
    assert f.get("/quote", {"symbol": "AAPL"})["c"] > 0

def test_missing_token_raises():
    import pytest
    with pytest.raises(ValueError):
        Finnhub("")
