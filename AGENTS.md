# AGENTS.md — TUI-CRYPTO

Greenfield repo. No code, toolchain, or tests exist yet. Only specs.

## Sources of truth

- `spesifikasi_mekanisme_filtering_alphaswing_us.md` — the 5-stage AlphaSwing funnel (formulas, thresholds, categories). Don't contradict it.
- `docs/superpowers/specs/2026-09-18-alphaswing-tui-design.md` — locked TUI design (resolves spec ambiguities: explicit sub-scores, batch/TTL budget). Follow it for implementation.

## Locked decisions

- Universe: US stocks only (watchlist 30–50 tickers in `watchlist.txt`, one per line). No crypto, no full S&P 500 in v1.
- Stack: Python + Textual. Single process: async Finnhub client → SQLite cache → pure scoring functions → Textual UI.
- Data: Finnhub (`FINNHUB_API_KEY` in `.env`, never commit). No key → deterministic mock mode so the TUI still opens.
- Efficiency budget: token-bucket 50 calls/min; startup batch 5 tickers/30s; routine refresh quote-only every `REFRESH_SEC` (default 300, min 60); candle 6h TTL, earnings/fundamentals 24h TTL.

## Planned layout (not yet created)

`app.py`, `scoring.py` (no I/O — pure functions only), `finnhub.py`, `cache.py`, `watchlist.txt`, `.env`, `tests/test_scoring.py`.

## Gotchas

- Finnhub free tier lacks options data → Pilar 5 scores insider component only (max 5) + `N/A-OPTIONS` flag. Don't fabricate scores for missing fields; score 0 + flag.
- Earnings blackout (`t_earnings <= 7`): `final = floor(pure × 0.70)` + lock category to `EARNINGS BLACKOUT`.
- RISK-OFF regime blocks new buys (banner + calculator warning) but the table stays browsable.
- `R_share <= 0` or NaN ATR → show `-`, position size 0. Never divide by zero.
