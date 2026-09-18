# Design Spec: TUI AlphaSwing US (Python + Textual + Finnhub)

- Date: 2026-09-18
- Status: Approved design, awaiting spec review
- Source of truth filtering: `spesifikasi_mekanisme_filtering_alphaswing_us.md` (5-stage funnel)
- Locked decisions: saham US saja; Python + Textual; Finnhub; hybrid cache (SQLite); auto-refresh 1–5 mnt; watchlist 30–50; single-process + cache; full dashboard v1

## 1. Goal & Non-Goals

Goal: TUI hemat resource untuk menampilkan rekomendasi swing saham US hasil funnel AlphaSwing (skor 0–100, kategori Ultra/High/Moderate/Blackout) dengan kalkulator posisi ATR.

Non-goals (v1): full S&P 500 + NASDAQ-100 (~600 ticker); realtime per-detik / websocket; chart candlestick; backtest; multi-user / server; broker order execution.

Success: buka <1 detik dari cache; idle ~0% CPU; RAM <150MB; tidak kena 429 Finnhub free pada refresh 5 mnt untuk 40 ticker; semua rumus Tahap 1–5 terimplementasi sebagai fungsi murni yang bisa diuji.

## 2. Architecture

Single process, 3 lapis:

```
Finnhub async client (rate-limited, batched)
  -> Cache SQLite (TTL per jenis data)
  -> Scoring engine (fungsi murni, tanpa I/O)
  -> Textual UI (render dari cache, update per-row)
```

Satu `asyncio` background worker melakukan fetch bertahap. Tidak ada thread pool, tidak ada daemon terpisah, tidak ada websocket di v1.

Skipped: dua-proses screener+TUI (tambah operasional), websocket streaming (boros API + kompleks). Add when: watchlist >200 atau butuh realtime <60 detik.

## 3. Components

### 3.1 Header regime (Tahap 1)
Input: daily SPY, QQQ, VIX via Finnhub candle/quote. Hitung EMA20, SMA50 untuk SPY (dan QQQ untuk display).
Aturan persis spec:
- RISK-ON: `P_SPY > EMA20 > SMA50 dan VIX < 18.0` → alokasi 100%.
- NEUTRAL: `SMA50 < P_SPY < EMA20 atau 18.0 <= VIX <= 23.0` → alokasi 50%, hanya setup pullback.
- RISK-OFF: `P_SPY < SMA50 atau VIX > 23.0` → alokasi 0%, blokir rekomendasi beli baru (tabel tetap tampil dengan banner merah).
Pilar 1 skor: 10 poin jika SPY & QQQ di atas EMA20 & SMA50; 5 poin jika VIX < 20.

### 3.2 Tabel utama + filter Tahap 5
Kolom: Ticker | Price | Skor | RS | VCP | Fund | Flow | Kategori | Earn(t).
Sort default skor descending. Filter pill: Semua | Ultra (skor>=90 & !blackout) | VCP Ready (`vcpStatus` contains "Ready") | RS_HIGH (`rsRating >= 85`). Search case-insensitive substring atas ticker/nama/sektor. Konjungsi `matchesCategory && matchesSearch` persis pseudocode spec.

### 3.3 Panel detail per ticker
- Breakdown 5 pilar dengan bobot 15/15/25/25/20 dan sub-kriteria (lihat §4).
- Earnings badge: BLOCKED (t<=7, skor×0.7 floor + label EARNINGS BLACKOUT), MONITORED (8–14), SAFE (>14).
- ATR block: ATR-14 (RMA/Wilder), SL = Price − 1.5×ATR, TP = Price + 3.0×ATR, Buy Zone [Price − 0.5×ATR, Price], R:R = (TP−Entry)/(Entry−SL). Layak jika R:R >= 2.0, tampil warning merah jika tidak.

### 3.4 Kalkulator posisi
Input: total modal akun, risiko % (default 1%). Rumus spec:
`D_risk = modal × risiko/100; R_share = Entry − SL; N = floor(D_risk / R_share)`.
Jika `R_share <= 0`, tampilkan error dan N = 0 (jaga pembagi nol).

### 3.5 Footer status
Umur cache, pemakaian API/menit (token-bucket counter), status LIVE/STALE, waktu refresh terakhir.

## 4. Scoring engine mapping (Finnhub)

Semua hitung di memori dari data cache. Tidak ada I/O di modul ini.

| Pilar | Bobot | Finnhub source | Aturan skor |
|---|---|---|---|
| 1. Macro | 15 | candle daily SPY/QQQ, VIX | 10 poin tren + 5 poin VIX<20 (§3.1) |
| 2. Mansfield RS | 15 | daily close stock + SPY, SMA50 dari ratio BP=Pstock/Pspy | RS = (BP/SMA50(BP)−1)×100; >=90→15; 85–89→12; 80–84→10; 75–79→8; 70–74→5; <70→0. Butuh ≥60 daily bar, jika kurang → skor 0 + flag `DATA_TIPIS` |
| 3. Teknikal/VCP | 25 | daily OHLCV + weekly (agregasi daily) | Pecah eksplisit: T1+T2+T3 terpenuhi→10; VDU vol T3 < 0.5×SMA20(vol)→8; MTF weekly close > SMA30-week & slope positif→7. Full = 25; parsial = jumlah komponen. `vcpStatus` = Ready jika T3+VDU terpenuhi |
| 4. Fundamental | 25 | recommendation, price-target, earnings surprise | Strong Buy/Buy→10; target rata-rata ≥+15%→8; EPS surprise positif terakhir→7. Field hilang → 0 + flag `N/A` (jangan ngarang) |
| 5. Smart money | 20 | option PCR jika tersedia, insider transactions 90 hari | Pecah eksplisit: PCR<0.45→8; unusual call sweep→7; zero insider sell 90d→5. Tier gratis tanpa opsi → hanya komponen insider (maks 5) + flag `N/A-OPTIONS` |

Blackout diterapkan setelah total murni: jika `t_earnings <= 7`, `final = floor(murni × 0.70)` + kunci kategori.

Kategori akhir: Ultra (≥90 & bebas blackout), High (85–89 & bebas), Moderate (<85), EARNINGS BLACKOUT (t≤7).

## 5. Data flow & efficiency budget

Startup: baca SQLite → render <1 detik → worker fetch urutan: VIX/SPY/QQQ dulu, lalu watchlist batch 5 ticker per 30 detik (tiap ticker ≤4 calls: quote+candle+earnings+fund ≈ 20 calls/30 detik = 40/menit, aman di bawah budget 50/menit; initial load 40 ticker ≈ 4 menit).
Refresh rutin tiap REFRESH_SEC hanya quote (1 call/ticker; 40 calls per 5 menit). Candle/fundamental/earnings ikut TTL panjang (6–24 jam), tidak di-fetch tiap refresh. Plus manual `R` (quote saja). Update hanya row berubah.
Rate limit: token-bucket 50 call/menit (sisakan margin), antrean FIFO, exponential backoff 2/4/8 detik saat 429, tetap sajikan cache + badge STALE.
Textual: `DataTable` virtualized, maksimal 9 kolom v1, tidak ada re-render penuh tiap tick.

## 6. Error handling

- 429/timeout/jaringan putus: backoff + tampilkan data cache + footer STALE + tidak crash.
- Tanpa `FINNHUB_API_KEY`: mode mock (data dummy deterministik) agar TUI tetap dibuka untuk dev.
- Earnings/fundamental/options hilang: skor parsial + flag, bukan gagal total.
- Regime RISK-OFF: banner merah + blokir aksi beli (kalkulator tampilkan peringatan), tabel tetap bisa dijelajah.
- `R_share <= 0` atau ATR NaN: SL/TP tampilkan `-`, N = 0.

## 7. Testing

Satu file `tests/test_scoring.py` (pytest, tanpa plugin): Mansfield pada data sintetis, VCP/VDU boundary, blackout ×0.7 + kunci label, ATR SL/TP/R:R + gate 2.0, sizing floor + div-nol, filter Tahap 5 (kategori + search). Trivial UI tidak diuji di v1.

## 8. Files & config (minimal)

```
app.py          # Textual app, layout, worker, keybindings
scoring.py      # fungsi murni Tahap 1–4 + filter Tahap 5 (tanpa I/O)
finnhub.py      # async client + token bucket + endpoint mapping
cache.py        # SQLite + TTL (quote/candle/earnings/fund)
watchlist.txt   # 30–50 ticker, satu per baris
.env            # FINNHUB_API_KEY=..., REFRESH_SEC=300
tests/test_scoring.py
```

Keybindings: `/` search, `1/2/3/4` filter pill, `R` refresh manual, `Enter` detail, `+/-` ubah risiko %, `q` quit.
Config: `REFRESH_SEC` default 300 (boleh 60–300, di bawah 60 ditolak agar hemat API).

// ponytail: global single worker + TTL kasar, bukan scheduler per-ticker. Per-ticker scheduler jika ticker >200 atau butuh freshness berbeda per kategori.
