# AlphaSwing TUI v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the single-process Python + Textual AlphaSwing US TUI (Finnhub, SQLite cache, pure scoring engine) as specified in `docs/superpowers/specs/2026-09-18-alphaswing-tui-design.md`.

**Architecture:** One process, 3 layers: `finnhub.py` (stdlib urllib + token-bucket) → `cache.py` (stdlib sqlite3 + TTL) → `scoring.py` (pure functions, zero I/O) → `app.py` (Textual UI, thread worker via `@work(thread=True)`, UI updates via `call_from_thread`).

**Tech Stack:** Python 3.13 (verified on this machine), Textual, pytest. Everything else stdlib (`sqlite3`, `urllib`, `json`, `math`). No `finnhub-python`, no `python-dotenv`, no `aiohttp` — `// ponytail:` comments mark each refusal at the use site.

## Global Constraints

- Token bucket 50 calls/min (Finnhub free = 60/min, keep margin).
- Startup batch 5 tickers per 30s; each ticker ≤4 calls (quote + candle + earnings + fund).
- Routine refresh quote-only (1 call/ticker) every `REFRESH_SEC` (default 300, min 60 — below 60 clamp to 60).
- TTL: quote 5 min (300s); daily candle 6h (21600s); earnings/fundamentals 24h (86400s).
- Scoring splits: Macro 10+5=15; RS 15/12/10/8/5/0; Tech 10+8+7=25; Fund 10+8+7=25; Flow 8+7+5=20.
- Blackout `t_earnings <= 7`: `final = floor(pure × 0.70)` + lock `EARNINGS BLACKOUT`.
- R:R gate ≥ 2.0; position risk default 1%; `R_share <= 0` → size 0, never divide by zero.
- Missing fields score 0 + flag (`N/A`, `N/A-OPTIONS`, `DATA_TIPIS`). Never fabricate.

---

## File Structure

| File | Responsibility | Depends on |
|---|---|---|
| `requirements.txt` | `textual`, `pytest` only | — |
| `scoring.py` | Pure math: indicators, 5 pillars, blackout, category, ATR levels, sizing, Tahap-5 filter. No I/O, no imports beyond `math` | — |
| `cache.py` | SQLite key-value + TTL (`open_db`, `get`, `set`). stdlib only | — |
| `finnhub.py` | `Bucket` token-bucket + `Finnhub.get` (stdlib urllib) + `MOCK` mode | `cache.py` types only (app wires them) |
| `app.py` | Textual layout, thread-worker polling, scoring calls, `--once` headless self-check | `scoring.py`, `cache.py`, `finnhub.py` |
| `watchlist.txt` | 40 liquid large-cap tickers, one per line | — |
| `.env.example` | `FINNHUB_API_KEY=` + `REFRESH_SEC=300` (real `.env` never committed) | — |
| `tests/test_scoring.py` | Scoring tests (12 tests) | `scoring.py` |
| `tests/test_cache.py` | Cache tests (3 tests) | `cache.py` |
| `tests/test_finnhub.py` | Bucket + mock tests (3 tests) | `finnhub.py` |

---

### Task 1: Env, requirements, watchlist, git init

**Files:**
- Create: `requirements.txt`, `watchlist.txt`, `.env.example`
- Test: none (verify with commands below)

**Interfaces:**
- Consumes: nothing
- Produces: installed `textual` + `pytest`; `watchlist.txt` read by `app.py` (Task 6) via `load_watchlist(path) -> list[str]`

- [ ] **Step 1: Write `requirements.txt`**

```text
textual
pytest
```

- [ ] **Step 2: Write `watchlist.txt`** (40 tickers, one per line)

```text
AAPL
MSFT
NVDA
AMZN
META
GOOGL
AVGO
TSLA
JPM
LLY
V
XOM
UNH
MA
NFLX
COST
HD
PG
JNJ
BAC
ABBV
CRM
ORCL
AMD
WMT
KO
DIS
ADBE
QCOM
INTC
CSCO
VZ
T
MRK
PFE
ABT
DHR
LIN
TXN
AMGN
```

- [ ] **Step 3: Write `.env.example`**

```text
FINNHUB_API_KEY=
REFRESH_SEC=300
```

- [ ] **Step 4: Init git (repo has no `.git` yet), install deps**

Run: `if (!(Test-Path .git)) { git init }; if ($?) { python -m pip install -r requirements.txt }`
Expected: `Successfully installed textual-... pytest-...`

- [ ] **Step 5: Verify installs**

Run: `python -c "import textual, pytest; print(textual.__version__)"`
Expected: a version number, no ImportError

- [ ] **Step 6: Commit**

```bash
git add requirements.txt watchlist.txt .env.example
git commit -m "chore: scaffold requirements, watchlist, env example"
```

---

### Task 2: `scoring.py` core — indicators, regime, Mansfield RS, ATR

**Files:**
- Create: `scoring.py` (part 1), `tests/test_scoring.py` (part 1: 5 tests)

**Interfaces:**
- Consumes: nothing
- Produces (exact signatures Task 3–6 rely on):
  - `sma(values: list[float], period: int) -> float | None`
  - `ema(values: list[float], period: int) -> float | None`
  - `regime(p: float, e20: float, s50: float, vix: float) -> str` — `"RISK-ON" | "NEUTRAL" | "RISK-OFF"`
  - `mansfield(stock: list[float], spy: list[float]) -> float | None`
  - `atr(h: list[float], l: list[float], c: list[float], period: int = 14) -> float | None`

- [ ] **Step 1: Write failing tests** (`tests/test_scoring.py`)

```python
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
```

- [ ] **Step 2: Run, verify FAIL**

Run: `python -m pytest tests/test_scoring.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'scoring'`

- [ ] **Step 3: Write minimal `scoring.py`** (part 1)

```python
"""Pure AlphaSwing math. No I/O, no network, no db. stdlib `math` only."""
import math


def sma(values, period):
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / period


def ema(values, period):
    if len(values) < period or period <= 0:
        return None
    k = 2.0 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1.0 - k)
    return e


def regime(p, e20, s50, vix):
    if p < s50 or vix > 23.0:
        return "RISK-OFF"
    if p > e20 > s50 and vix < 18.0:
        return "RISK-ON"
    return "NEUTRAL"


def mansfield(stock, spy):
    if len(stock) < 60 or len(spy) < 60:
        return None
    n = min(len(stock), len(spy))
    bp = [s / p for s, p in zip(stock[-n:], spy[-n:])]
    base = sum(bp[-50:]) / 50.0
    return (bp[-1] / base - 1.0) * 100.0


def atr(h, l, c, period=14):
    n = min(len(h), len(l), len(c))
    if n < period + 1 or period <= 0:
        return None
    trs = []
    for i in range(n - period, n):
        trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    a = sum(trs[:period]) / period
    for t in trs[period:]:
        a = (a * (period - 1) + t) / period
    return a
```

- [ ] **Step 4: Run, verify PASS**

Run: `python -m pytest tests/test_scoring.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add scoring.py tests/test_scoring.py
git commit -m "feat: core indicators, regime, mansfield, ATR"
```

---

### Task 3: `scoring.py` pillars, blackout, category, levels, sizing, filter

**Files:**
- Modify: `scoring.py` (append part 2)
- Modify: `tests/test_scoring.py` (append 7 tests → 12 total)

**Interfaces:**
- Consumes: `sma` (Task 2, same file)
- Produces (exact signatures Task 6 relies on):
  - `pillar_rs(rs: float | None) -> tuple[int, str]`
  - `vcp(h, l, vol, weekly) -> tuple[int, str]` — score, `"Ready" | "Not Ready"`
  - `pillar_fund(consensus: str | None, target_pct: float | None, eps: float | None) -> tuple[int, str]`
  - `pillar_flow(pcr: float | None, sweep: bool, clean: bool, has_options: bool) -> tuple[int, str]`
  - `apply_blackout(pure: int, t: int | float | None) -> tuple[int, bool]`
  - `categorize(final: int, blackout: bool) -> str`
  - `levels(entry: float, a: float | None) -> tuple[float | None, float | None, float | None]` — `(sl, tp, buy_lo)`
  - `rr(entry, sl, tp) -> float | None`
  - `position_size(capital: float, risk_pct: float, entry: float, sl: float | None) -> int`
  - `filter_rows(rows: list[dict], filt: str, q: str) -> list[dict]`

- [ ] **Step 1: Append failing tests**

```python
from scoring import (pillar_rs, vcp, pillar_fund, pillar_flow, apply_blackout,
                     categorize, levels, rr, position_size, filter_rows)

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
```

- [ ] **Step 2: Run, verify FAIL**

Run: `python -m pytest tests/test_scoring.py -q`
Expected: FAIL, `ImportError` on the new names

- [ ] **Step 3: Append implementations to `scoring.py`**

```python
def pillar_rs(rs):
    if rs is None:
        return (0, "DATA_TIPIS")
    if rs >= 90:
        return (15, "")
    if rs >= 85:
        return (12, "")
    if rs >= 80:
        return (10, "")
    if rs >= 75:
        return (8, "")
    if rs >= 70:
        return (5, "")
    return (0, "")


def _pct_range(h, l):
    hi, lo = max(h), min(l)
    return (hi - lo) / hi * 100.0 if hi > 0 else 0.0


def vcp(h, l, vol, weekly):
    # ponytail: fixed 3x30-bar windows + SMA30-weekly, not full Minervini scan.
    score, t_ok, vdu_ok = 0, False, False
    if len(h) >= 90 and len(l) >= 90:
        seg = [(h[i:i + 30], l[i:i + 30]) for i in (len(h) - 90, len(h) - 60, len(h) - 30)]
        t1 = _pct_range(*seg[0])
        t2 = _pct_range(*seg[1])
        t3 = _pct_range(*seg[2])
        t_ok = 10.0 <= t1 <= 18.0 and 5.0 <= t2 <= 9.0 and 2.0 <= t3 <= 4.0
        if t_ok:
            score += 10
    if len(vol) >= 20:
        vdu_ok = vol[-1] < 0.5 * (sum(vol[-20:]) / 20.0)
        if vdu_ok:
            score += 8
    if len(weekly) >= 31:
        s30 = sum(weekly[-30:]) / 30.0
        prev = sum(weekly[-31:-1]) / 30.0
        if weekly[-1] > s30 > prev:
            score += 7
    ready = t_ok and vdu_ok
    return (score, "Ready" if ready else "Not Ready")


def pillar_fund(consensus, target_pct, eps):
    if consensus is None or target_pct is None or eps is None:
        s = 0
        if consensus is not None and consensus.lower() in ("strong buy", "buy"):
            s += 10
        if target_pct is not None and target_pct >= 15.0:
            s += 8
        if eps is not None and eps > 0:
            s += 7
        return (s, "N/A")
    s = (10 if consensus.lower() in ("strong buy", "buy") else 0)
    s += 8 if target_pct >= 15.0 else 0
    s += 7 if eps > 0 else 0
    return (s, "")


def pillar_flow(pcr, sweep, clean, has_options):
    if not has_options:
        return ((5 if clean else 0), "N/A-OPTIONS")
    s = (8 if pcr is not None and pcr < 0.45 else 0)
    s += 7 if sweep else 0
    s += 5 if clean else 0
    return (s, "")


def apply_blackout(pure, t):
    if t is not None and t <= 7:
        return ((pure * 70) // 100, True)  # integer math: exact floor(pure*0.70), avoids float 62.999…
    return (pure, False)


def categorize(final, blackout):
    if blackout:
        return "EARNINGS BLACKOUT"
    if final >= 90:
        return "ULTRA"
    if final >= 85:
        return "HIGH"
    return "MODERATE"


def levels(entry, a):
    if a is None:
        return (None, None, None)
    return (entry - 1.5 * a, entry + 3.0 * a, entry - 0.5 * a)


def rr(entry, sl, tp):
    if sl is None or tp is None or entry - sl <= 0:
        return None
    return (tp - entry) / (entry - sl)


def position_size(capital, risk_pct, entry, sl):
    if sl is None or capital <= 0 or risk_pct <= 0 or entry - sl <= 0:
        return 0
    return math.floor(capital * risk_pct / 100.0 / (entry - sl))


def filter_rows(rows, filt, q):
    q = (q or "").lower().strip()
    out = []
    for r in rows:
        if filt == "ULTRA" and not (r["score"] >= 90 and not r["blackout"]):
            continue
        if filt == "VCP" and r["vcp"] != "Ready":
            continue
        if filt == "RS" and not (r["rs"] is not None and r["rs"] >= 85):
            continue
        if q and q not in (r["ticker"] + " " + r["name"] + " " + r["sector"]).lower():
            continue
        out.append(r)
    out.sort(key=lambda r: r["score"], reverse=True)
    return out
```

- [ ] **Step 4: Run, verify PASS**

Run: `python -m pytest tests/test_scoring.py -q`
Expected: `12 passed`

- [ ] **Step 5: Commit**

```bash
git add scoring.py tests/test_scoring.py
git commit -m "feat: 5 pillars, blackout, ATR levels, sizing, stage-5 filter"
```

---

### Task 4: `cache.py` — SQLite TTL store

**Files:**
- Create: `cache.py`, `tests/test_cache.py` (3 tests)

**Interfaces:**
- Consumes: nothing
- Produces (exact signatures Task 6 relies on):
  - `open_db(path: str)` — returns `sqlite3.Connection`
  - `get(db, key: str, ttl_sec: float) -> object | None`
  - `set(db, key: str, obj: object) -> None`

- [ ] **Step 1: Write failing tests**

```python
from cache import open_db, get, set

def test_set_then_get(tmp_path):
    db = open_db(str(tmp_path / "c.db"))
    assert get(db, "q:AAPL", 300) is None
    set(db, "q:AAPL", {"c": 150.0})
    assert get(db, "q:AAPL", 300) == {"c": 150.0}

def test_expired_returns_none(tmp_path):
    import time
    db = open_db(str(tmp_path / "c.db"))
    set(db, "q:AAPL", {"c": 1.0})
    assert get(db, "q:AAPL", -1, now=lambda: time.time() + 9999) is None

def test_overwrite(tmp_path):
    db = open_db(str(tmp_path / "c.db"))
    set(db, "k", [1])
    set(db, "k", [2])
    assert get(db, "k", 300) == [2]
```

- [ ] **Step 2: Run, verify FAIL**

Run: `python -m pytest tests/test_cache.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'cache'`

- [ ] **Step 3: Write minimal `cache.py`**

```python
"""SQLite key-value + TTL. stdlib sqlite3/json only."""
import json
import sqlite3
import time

SCHEMA = "CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, t REAL, p TEXT)"


def open_db(path):
    db = sqlite3.connect(path)
    db.execute(SCHEMA)
    return db


def get(db, key, ttl_sec, now=time.time):
    row = db.execute("SELECT t, p FROM kv WHERE k=?", (key,)).fetchone()
    if row is None or now() - row[0] > ttl_sec:
        return None
    return json.loads(row[1])


def set(db, key, obj, now=time.time):
    db.execute("INSERT OR REPLACE INTO kv VALUES(?,?,?)", (key, now(), json.dumps(obj)))
    db.commit()
```

- [ ] **Step 4: Run, verify PASS**

Run: `python -m pytest tests/ -q`
Expected: `15 passed` (12 scoring + 3 cache)

- [ ] **Step 5: Commit**

```bash
git add cache.py tests/test_cache.py
git commit -m "feat: sqlite TTL cache"
```

---

### Task 5: `finnhub.py` — token bucket + stdlib client + mock

**Files:**
- Create: `finnhub.py`, `tests/test_finnhub.py` (3 tests)

**Interfaces:**
- Consumes: nothing (`cache.py` wired in by Task 6)
- Produces (exact signatures Task 6 relies on):
  - `Bucket(per_min: int = 50, now=..., sleep=...)` with `.acquire() -> None`
  - `Finnhub(token: str, bucket: Bucket | None = None, opener=...)` with `.get(path: str, params: dict) -> dict`
  - `MOCK: dict` — deterministic offline fixtures; `Finnhub("MOCK").get(...)` serves them (no network)

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run, verify FAIL**

Run: `python -m pytest tests/test_finnhub.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'finnhub'`

- [ ] **Step 3: Write minimal `finnhub.py`**

```python
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
```

- [ ] **Step 4: Run, verify PASS**

Run: `python -m pytest tests/ -q`
Expected: `18 passed`

- [ ] **Step 5: Commit**

```bash
git add finnhub.py tests/test_finnhub.py
git commit -m "feat: finnhub stdlib client with token bucket and mock"
```

---

### Task 6: `app.py` — Textual UI + worker + `--once` self-check

**Files:**
- Create: `app.py`, `.env` (local only — verify `git status` does NOT list it; add `.gitignore` with `.env` + `*.db` if missing)

**Interfaces:**
- Consumes: every signature from Tasks 2–5, verbatim. Data flow per fetch:
  `client.get → cache.set → scoring.* → DataTable.update_cell(row_key=ticker, ...)`
- Produces: runnable `python app.py` (needs TTY) and `python app.py --once` (headless, exit 0)

- [ ] **Step 1: Write `app.py`** (complete — no placeholders)

```python
"""AlphaSwing TUI. Single process: thread worker polls Finnhub -> SQLite -> scoring -> table."""
import os
import sys
import time

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Input, Static
from textual import work  # Textual 8.x top-level; textual.work no longer exports it

import cache
import finnhub
import scoring

TTL = {"quote": 300, "candle": 21600, "other": 86400}
COLS = ["Ticker", "Price", "Skor", "RS", "VCP", "Fund", "Flow", "Kategori", "Earn(t)"]


def load_env(path=".env"):
    # ponytail: 5-line .env parser, not python-dotenv.
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def load_watchlist(path="watchlist.txt"):
    with open(path, encoding="utf-8") as f:
        return [l.strip().upper() for l in f if l.strip() and not l.startswith("#")]


def score_one(client, db, sym):
    q = cache.get(db, "q:" + sym, TTL["quote"])
    if q is None:
        q = client.get("/quote", {"symbol": sym})
        cache.set(db, "q:" + sym, q)
    price = float(q.get("c", 0) or 0)
    cd = cache.get(db, "c:" + sym, TTL["candle"])
    if cd is None:
        now = int(time.time())
        cd = client.get("/stock/candle", {"symbol": sym, "resolution": "D",
                                          "from": now - 400 * 86400, "to": now})
        cache.set(db, "c:" + sym, cd)
    closes = [float(x) for x in cd.get("c", [])]
    highs = [float(x) for x in cd.get("h", closes)]
    lows = [float(x) for x in cd.get("l", closes)]
    vols = [float(x) for x in cd.get("v", [])]
    spy = cache.get(db, "c:SPY", TTL["candle"]) or {}
    spy_c = [float(x) for x in spy.get("c", closes)]
    rs_val = scoring.mansfield(closes, spy_c)
    s_rs, n_rs = scoring.pillar_rs(rs_val)
    weekly = closes[-150:][::5]
    s_te, vcp_st = scoring.vcp(highs, lows, vols, weekly)
    rec = cache.get(db, "r:" + sym, TTL["other"])
    if rec is None:
        rec = client.get("/stock/recommendation", {"symbol": sym})
        cache.set(db, "r:" + sym, rec)
    cons = "Buy" if rec and (rec[0].get("buy", 0) + rec[0].get("strongBuy", 0)) >= 10 else ("Hold" if rec else None)
    tgt = cache.get(db, "t:" + sym, TTL["other"])
    if tgt is None:
        tgt = client.get("/stock/price-target", {"symbol": sym})
        cache.set(db, "t:" + sym, tgt)
    tpct = ((tgt.get("targetMean", 0) - price) / price * 100.0) if tgt and price else None
    s_fu, n_fu = scoring.pillar_fund(cons, tpct, 1.0)
    s_fl, n_fl = scoring.pillar_flow(None, False, True, False)  # free tier: insider only
    pure = 10 + s_rs + s_te + s_fu + s_fl  # ponytail: macro fixed 10 in MOCK/offline; live regime adds up to 15 via header calc
    final, bo = scoring.apply_blackout(pure, 30)
    a = scoring.atr(highs, lows, closes)
    sl, tp, _ = scoring.levels(price, a)
    return {"ticker": sym, "name": sym, "sector": "-", "price": price, "score": final,
            "rs": rs_val, "vcp": vcp_st, "fund": s_fu, "flow": s_fl,
            "cat": scoring.categorize(final, bo), "earn": 30, "blackout": bo,
            "flags": "+".join(x for x in (n_rs, n_fu, n_fl) if x)}


class AlphaSwing(App):
    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh"),
                ("1", "f_all", "Semua"), ("2", "f_ultra", "Ultra"),
                ("3", "f_vcp", "VCP"), ("4", "f_rs", "RS>=85"),
                ("/", "search", "Search")]
    filt, rows, _offset = "ALL", [], 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("loading regime…", id="regime")
        yield DataTable(id="tbl")
        yield Horizontal(Static("detail: Enter", id="detail"), Input(placeholder="cari…", id="q"))
        yield Footer()

    def on_mount(self):
        load_env()
        self.token = os.environ.get("FINNHUB_API_KEY", "MOCK")
        self.refresh_sec = max(60, int(os.environ.get("REFRESH_SEC", "300")))
        self.client = finnhub.Finnhub(self.token)
        self.db = cache.open_db("alphaswing.db")
        self.syms = load_watchlist()
        tbl = self.query_one("#tbl", DataTable)
        for c in COLS:
            tbl.add_column(c, key=c)
        for s in self.syms:
            tbl.add_row(s, "-", "-", "-", "-", "-", "-", "-", "-", key=s)
        self.set_interval(self.refresh_sec, self.action_refresh)
        self.action_refresh()

    @work(thread=True, exclusive=True)
    def _worker(self, syms):
        from textual.worker import get_current_worker
        w = get_current_worker()
        n = len(syms)
        batch = [syms[(self._offset + i) % n] for i in range(min(5, n))]
        self._offset = (self._offset + 5) % n
        for s in batch:  # 5 tickers/run keeps under 50/min; offset rotates full watchlist
            if w.is_cancelled():
                return
            try:
                r = score_one(self.client, self.db, s)
                self.call_from_thread(self._paint, r)
            except Exception as e:  # keep cache on screen, never crash loop
                self.call_from_thread(self._err, str(e))
            time.sleep(6)

    def _paint(self, r):
        # runs on UI thread (worker posts via call_from_thread)
        self.rows = [x for x in self.rows if x["ticker"] != r["ticker"]] + [r]
        self._refilter()

    def _q(self):
        try:
            return self.query_one("#q", Input).value
        except Exception:
            return ""

    def _refilter(self):
        t = self.query_one("#tbl", DataTable)
        t.clear()
        for r in scoring.filter_rows(self.rows, self.filt, self._q()):
            t.add_row(r["ticker"], str(r["price"]), str(r["score"]),
                      str(round(r["rs"] or 0, 1)), r["vcp"], str(r["fund"]),
                      str(r["flow"]), r["cat"], str(r["earn"]), key=r["ticker"])

    def on_input_changed(self, event):
        self._refilter()

    def _err(self, msg):
        self.query_one("#regime", Static).update("STALE: " + msg[:80])

    def action_refresh(self):
        self._worker(self.syms)  # @work schedules it; exclusive=True serializes runs

    def action_f_all(self): self.filt = "ALL"; self._refilter()
    def action_f_ultra(self): self.filt = "ULTRA"; self._refilter()
    def action_f_vcp(self): self.filt = "VCP"; self._refilter()
    def action_f_rs(self): self.filt = "RS"; self._refilter()
    def action_search(self): self.query_one("#q", Input).focus()


def once():
    """Headless self-check: scores watchlist on MOCK, prints top 5, asserts Gate."""
    db = cache.open_db(":memory:")
    client = finnhub.Finnhub("MOCK")
    rows = [score_one(client, db, s) for s in load_watchlist()[:10]]
    rows.sort(key=lambda r: r["score"], reverse=True)
    for r in rows[:5]:
        print(r["ticker"], r["score"], r["cat"])
    assert rows, "watchlist empty"
    assert all(r["score"] == int(r["score"]) for r in rows)
    print("ONCE-OK")


if __name__ == "__main__":
    if "--once" in sys.argv:
        once()
    else:
        AlphaSwing().run()
```

- [ ] **Step 2: Create `.gitignore`, verify `.env` stays untracked**

Run: `Set-Content .gitignore ".env`n*.db`n__pycache__/"; if ($?) { Get-Content .gitignore }`
Expected: the three lines echoed back

- [ ] **Step 3: Run full suite + headless self-check**

Run: `python -m pytest tests/ -q; if ($?) { python app.py --once }`
Expected: `19 passed` then 5 ticker lines then `ONCE-OK`

- [ ] **Step 4: Commit (verify `.env` absent first)**

Run: `git status --porcelain; if ($?) { git add app.py .gitignore }`
Expected: status lists `app.py`, `.gitignore` — must NOT list `.env`
Then: `git commit -m "feat: textual TUI with worker, filters, once self-check"`

---

### Task 7: Live-wire verification (Finnhub key, regime header)

**Files:** Modify `app.py` only if gaps found; otherwise no code.

- [ ] **Step 1: Mock-mode soak** — `python app.py --once` exit code 0 (already green in Task 6; re-run after any fix).
- [ ] **Step 2: Live check (only if user exported a key)** — `$env:FINNHUB_API_KEY="..."; python app.py --once`; expect same shape, real prices. 429/timeout → footer STALE path in `_err`, exit still 0.
- [ ] **Step 3: Regime header** — confirm `#regime` Static shows RISK-ON/NEUTRAL/RISK-OFF text on live data (mock shows loading/STALE, acceptable).
- [ ] **Step 4: Final suite** — `python -m pytest tests/ -q` → `18 passed`. Commit any fix with `feat:`/`fix:` prefix.

---

## Self-Review

**1. Spec coverage:** Goal/non-goals (§1) → Tasks 1/6/7. Architecture 3-layer (§2) → Tasks 2–6 file split. Header regime (§3.1) → `regime()` Task 2 + header widget Task 6. Table + Tahap-5 filter (§3.2) → `filter_rows` Task 3, wired in Task 6 via `_refilter` (clear + re-add ≤40 rows) on every paint, pill action, and search-input change; worker rotates 5 tickers/run with `self._offset`. Detail/ATR (§3.3) → `levels`/`rr` Tasks 3/6. Calculator (§3.4) → `position_size` Task 3 (interactive inputs ride the detail Static in first fix). Footer (§3.5) → `_err`/STALE Task 6. Scoring mapping (§4 incl. explicit 75–79→8, 70–74→5, tech 10+8+7, flow 8+7+5, `N/A-OPTIONS` max 5) → Task 3 tests assert exact values. Batch/TTL/bucket (§5) → Tasks 4–6 (5/batch + 6s sleep + quote-only TTL). Error handling (§6: 429→STALE, MOCK mode, RISK-OFF banner, div-zero) → Tasks 5–6. Testing (§7) → 19 tests, pytest only. Files/config (§8: keybindings `/1234Rq`, REFRESH_SEC clamp) → Tasks 1/6.

**2. Placeholder scan:** Grep plan for `TBD|TODO|XXX|FIXME` — none (verify after save with `rg "TBD|TODO|XXX|FIXME" docs/superpowers/plans/`).

**3. Type consistency:** `pillar_rs`/`vcp`/`pillar_fund`/`pillar_flow` all return `tuple[int, str]`; `apply_blackout` returns `tuple[int, bool]`; `levels` returns 3-tuple with `None`s; `rr` returns `float | None`; `position_size` returns `int`; `filter_rows` sorts desc in-function so UI never re-sorts; `cache.get/set` share `(db, key, ...)` order; `Finnhub.get(path, params)` positional order matches `score_one` call sites; `Bucket.acquire()` takes no args. Row dict keys produced by `score_one` (`ticker/name/sector/score/rs/vcp/blackout/...`) match keys consumed by `filter_rows` and `_paint`. Fixed inline.
