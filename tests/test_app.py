import urllib.error
import asyncio

from finnhub import Finnhub
import cache
from app import score_one, load_watchlist
import app as appmod

def test_score_one_mock():
    db = cache.open_db(":memory:")
    r = score_one(Finnhub("MOCK"), db, "AAPL")
    assert r["score"] == 35
    assert r["cat"] == "MODERATE"
    assert r["blackout"] is False
    assert r["fund"] == 18 and r["flow"] == 0
    assert "N/A" in r["flags"] and "N/A-OPTIONS" in r["flags"]


class GatedClient:
    """Mimics a key whose plan forbids candle + price-target (HTTP 403)."""

    def __init__(self):
        self.inner = Finnhub("MOCK")

    def get(self, path, params):
        if path in ("/stock/candle", "/stock/price-target"):
            raise urllib.error.HTTPError("http://x", 403, "Forbidden", {}, None)
        return self.inner.get(path, params)


def test_score_one_degrades_on_gated_endpoints():
    db = cache.open_db(":memory:")
    r = score_one(GatedClient(), db, "AAPL")
    assert r["price"] == 150.0
    assert r["rs"] is None and r["vcp"] == "Not Ready"
    assert r["fund"] == 10 and r["flow"] == 0
    assert r["score"] == 10 + 0 + 0 + 10 + 0
    assert "DATA_TIPIS" in r["flags"] and "N/A" in r["flags"]


def test_worker_paints_rows_headless(monkeypatch):
    """Regression: worker must survive cancellation check (is_cancelled is a
    property in Textual 8.x) and paint rows. Uses run_test pilot, MOCK data."""
    monkeypatch.setenv("FINNHUB_API_KEY", "MOCK")

    async def go():
        a = appmod.AlphaSwing()
        async with a.run_test() as pilot:
            await pilot.pause(8)
            return list(a.rows)

    assert len(asyncio.run(go())) >= 1
