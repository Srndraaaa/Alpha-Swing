"""AlphaSwing TUI. Single process: thread worker polls Finnhub -> SQLite -> scoring -> table."""
import os
import sys
import time
import urllib.error

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Input, Static

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
        try:
            now = int(time.time())
            cd = client.get("/stock/candle", {"symbol": sym, "resolution": "D",
                                              "from": now - 400 * 86400, "to": now})
        except urllib.error.HTTPError:
            cd = {"c": [], "h": [], "l": [], "v": []}  # plan-gated: degrade, indicators 0 + DATA_TIPIS
        else:
            cache.set(db, "c:" + sym, cd)
    closes = [float(x) for x in cd.get("c", [])]
    highs = [float(x) for x in cd.get("h", closes)]
    lows = [float(x) for x in cd.get("l", closes)]
    vols = [float(x) for x in cd.get("v", [])]
    spy = cache.get(db, "c:SPY", TTL["candle"]) or {}
    spy_c = [float(x) for x in spy.get("c", [])]
    rs_val = scoring.mansfield(closes, spy_c)
    s_rs, n_rs = scoring.pillar_rs(rs_val)
    weekly = closes[-155:][::5]
    s_te, vcp_st = scoring.vcp(highs, lows, vols, weekly)
    rec = cache.get(db, "r:" + sym, TTL["other"])
    if rec is None:
        rec = client.get("/stock/recommendation", {"symbol": sym})
        cache.set(db, "r:" + sym, rec)
    cons = "Buy" if rec and (rec[0].get("buy", 0) + rec[0].get("strongBuy", 0)) >= 10 else ("Hold" if rec else None)
    tgt = cache.get(db, "t:" + sym, TTL["other"])
    if tgt is None:
        try:
            tgt = client.get("/stock/price-target", {"symbol": sym})
        except urllib.error.HTTPError:
            tgt = {}  # plan-gated: fund scores partial + N/A
        else:
            cache.set(db, "t:" + sym, tgt)
    tpct = ((tgt.get("targetMean", 0) - price) / price * 100.0) if tgt and price else None
    s_fu, n_fu = scoring.pillar_fund(cons, tpct, None)
    ins = cache.get(db, "i:" + sym, TTL["other"])
    if ins is None:
        ins = client.get("/stock/insider-transactions", {"symbol": sym})
        cache.set(db, "i:" + sym, ins)
    txns = ins.get("data", []) if isinstance(ins, dict) else (ins if isinstance(ins, list) else [])
    clean = bool(txns) and not any((t.get("change", 0) or 0) < 0 or t.get("transactionCode") == "S" for t in txns if isinstance(t, dict))
    s_fl, n_fl = scoring.pillar_flow(None, False, clean, False)  # free tier: insider only
    pure = 10 + s_rs + s_te + s_fu + s_fl  # ponytail: macro fixed 10 offline; live regime adds via header
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
        self._slow = False
        self._timer = self.set_interval(30, self.action_refresh)
        self.action_refresh()

    @work(thread=True, exclusive=True)
    def _worker(self, syms):
        from textual.worker import get_current_worker
        w = get_current_worker()
        n = len(syms)
        if n == 0:
            return
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
        if not self._slow and len(self.rows) >= len(self.syms):
            self._slow = True
            self._timer.stop()
            self._timer = self.set_interval(self.refresh_sec, self.action_refresh)
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
    """Headless self-check: scores watchlist on MOCK, prints top 5, asserts gate."""
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
