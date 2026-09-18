"""Finnhub REST via stdlib urllib + token-bucket. No third-party client."""
import json
import time
import urllib.parse
import urllib.request

BASE = "https://finnhub.io/api/v1"

# ponytail: canned fixtures, not a mock framework. Offline dev + --once smoke.
MOCK = {
    "/quote": {"c": 150.0, "pc": 148.0},
    "/stock/candle": {"s": "ok", "c": [100.0 + i * 0.5 for i in range(200)],
                      "h": [101.0 + i * 0.5 for i in range(200)],
                      "l": [99.0 + i * 0.5 for i in range(200)],
                      "v": [1000.0] * 200, "t": list(range(200))},
    "/calendar/earnings": {"earningsCalendar": []},
    "/stock/recommendation": [{"buy": 20, "strongBuy": 10, "sell": 1, "strongSell": 0, "hold": 5}],
    "/stock/price-target": {"targetMean": 180.0, "lastPrice": 150.0},
    "/stock/insider-transactions": {"data": []},
}


class Bucket:
    def __init__(self, per_min=50, now=time.monotonic, sleep=time.sleep):
        self.rate = per_min / 60.0
        self.cap = float(per_min)
        self.tok = float(per_min)
        self.last = now()
        self._now = now
        self._sleep = sleep

    def acquire(self):
        now = self._now()
        self.tok = min(self.cap, self.tok + (now - self.last) * self.rate)
        self.last = now
        if self.tok >= 1.0:
            self.tok -= 1.0
            return
        wait = (1.0 - self.tok) / self.rate
        self._sleep(wait)
        self.tok = 0.0
        self.last = self._now()


class Finnhub:
    def __init__(self, token, bucket=None, opener=urllib.request.urlopen):
        if not token:
            raise ValueError("FINNHUB_API_KEY missing (use token MOCK for offline)")
        self.token = token
        self.bucket = bucket or Bucket()
        self._open = opener

    def get(self, path, params):
        if self.token == "MOCK":
            return MOCK.get(path, {})
        self.bucket.acquire()
        qs = urllib.parse.urlencode({"token": self.token, **params})
        req = urllib.request.Request(BASE + path + "?" + qs, method="GET")
        with self._open(req, timeout=15) as resp:
            return json.load(resp)
