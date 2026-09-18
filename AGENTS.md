# AGENTS.md — TUI-CRYPTO (Alpha-Swing)

Python + Textual stock-screener TUI. Single process: thread worker (stdlib `urllib`) → SQLite cache → pure scoring → Textual table. Remote: `git@github.com:Srndraaaa/Alpha-Swing.git`, branch `master`.

## Sources of truth

- `spesifikasi_mekanisme_filtering_alphaswing_us.md` — 5-stage funnel (formulas, thresholds). Don't contradict it.
- `docs/superpowers/specs/2026-09-18-alphaswing-tui-design.md` — locked design (explicit sub-scores, batch/TTL budget).
- `docs/superpowers/plans/2026-09-18-alphaswing-tui-v1.md` — implementation plan with verbatim code.

## Commands (PowerShell 5.1; chain with `; if ($?)`, never `&&`)

- Install: `python -m pip install -r requirements.txt` (only `textual`, `pytest`; everything else stdlib)
- Tests: `python -m pytest tests/ -q` (20 tests, must stay green)
- Headless check: `python app.py --once` (MOCK mode, prints top-5 + `ONCE-OK`, exit 0)
- Live: copy `.env.example` → `.env`, set `FINNHUB_API_KEY`, run `python app.py`
- Interactive TUI needs a real TTY — agents can't open it; `--once` is the verification.

## Layout

`app.py` (UI + worker + `score_one` wiring), `scoring.py` (**no I/O — pure functions only**), `finnhub.py` (`Bucket` + `Finnhub.get` + `MOCK`), `cache.py` (`open_db`/`get`/`set` + TTL), `watchlist.txt` (40 tickers), `tests/` (`test_scoring.py`, `test_cache.py`, `test_finnhub.py`, `test_app.py`).

## Gotchas (all bitten before — don't regress)

- Textual 8.x: `from textual import work`, NOT `from textual.work import` (absent). `get_current_worker` still lives in `textual.worker`. `Worker.is_cancelled` is a **property** — calling it throws `TypeError: 'bool' object is not callable` and kills every worker run.
- `cache.open_db` uses `check_same_thread=False` because the exclusive worker is the only thread that ever queries; the UI thread never touches the DB. If UI code ever queries, switch to per-thread connections.
- VCP filter must be `!= "Ready"` — `"Ready" in "Not Ready"` is True (substring trap, also in spec's JS pseudocode).
- Blackout math must be integer `(pure * 70) // 100` — `floor(90 * 0.70)` gives 62 via float `62.999…`, spec wants 63.
- `vcp()` needs ≥31 weekly bars; `app.py` slices `closes[-155:][::5]` (a 150-bar tail yields only 30 and silently drops the +7 MTF points).
- Missing data scores 0 + flag (`N/A`, `N/A-OPTIONS`, `DATA_TIPIS`) — never fabricate. Free tier has no options: Pilar 5 = insider only (max 5). `score_one` passes `eps=None`, `clean=False` unless proven.
- Some keys/plans gate `/stock/candle` + `/stock/price-target` (HTTP 403): `score_one` catches `HTTPError` per endpoint and degrades to empty series/dict (never cached), so RS/VCP/ATR score 0 + `DATA_TIPIS` while quote/fund/insider keep working.
- `R_share <= 0` or NaN ATR → size 0, never divide by zero. `REFRESH_SEC` clamps to min 60.
- Efficiency: token-bucket 50/min; worker batch 5 tickers + 6s sleep with rotating `_offset`; fast 30s timer until full coverage, then `REFRESH_SEC` (default 300). Don't reintroduce per-second polling.
- `.env` never committed (gitignored with `*.db`, `__pycache__/`). No key → deterministic MOCK mode.
- SSH from Windows OpenSSH 9.5 fails against github.com (KEX); push via Git Bash (bundled OpenSSH 10.x) or HTTPS.
