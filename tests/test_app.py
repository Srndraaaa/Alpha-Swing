from finnhub import Finnhub
import cache
from app import score_one, load_watchlist

def test_score_one_mock():
    db = cache.open_db(":memory:")
    r = score_one(Finnhub("MOCK"), db, "AAPL")
    assert r["score"] == 35
    assert r["cat"] == "MODERATE"
    assert r["blackout"] is False
    assert r["fund"] == 18 and r["flow"] == 0
    assert "N/A" in r["flags"] and "N/A-OPTIONS" in r["flags"]
