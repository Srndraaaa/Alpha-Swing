# Spesifikasi Teknis: Arsitektur & Mekanisme Filtering AlphaSwing US v3.0

Dokumen ini mendefinisikan secara menyeluruh seluruh tingkatan penyaringan (*filtering pipeline*), formula matematis, aturan diskualifikasi (*hard stop*), serta logika interaktif yang digunakan oleh mesin **AlphaSwing US** untuk menyeleksi peluang transaksi *swing trading* berstandar institusional (*institutional-grade*).

---

## 1. Filosofi & Hierarki Filtering (Top-Down Funnel)

AlphaSwing US tidak menggunakan penyaringan satu lapis (*single-layer scanning*). Sistem mengadopsi model **Corong Bertingkat (Top-Down Funnel)** yang memastikan bahwa saham individu hanya dinilai jika iklim pasar makro mendukung, serta mendiskualifikasi setup teknikal jika terdapat risiko fundamental fatal.

```
       [ SEMESTA SAHAM: S&P 500 & NASDAQ-100 (Large & Mid-Cap) ]
                                  │
                                  ▼
     ┌──────────────────────────────────────────────────────────┐
     │ TAHAP 1: TOP-DOWN MARKET REGIME FILTER (MACRO GATEKEEPER)│
     │ Evaluasi SPY, QQQ, & VIX -> Mengatur Kuota Alokasi Modal │
     └────────────────────────────┬─────────────────────────────┘
                                  │ Lolos (Market Risk-On / Neutral)
                                  ▼
     ┌──────────────────────────────────────────────────────────┐
     │ TAHAP 2: EARNINGS BLACKOUT GUARD (EVENT RISK SHIELD)     │
     │ Eliminasi saham dengan jadwal rilis kinerja <= 7 Hari    │
     └────────────────────────────┬─────────────────────────────┘
                                  │ Lolos (Bebas Risiko Gap Biner)
                                  ▼
     ┌──────────────────────────────────────────────────────────┐
     │ TAHAP 3: 5-PILLAR MULTI-FACTOR CONFLUENCE SCORING ENGINE │
     │ Penilaian 100 Poin: Macro, RS, VCP, Funda, Smart Money   │
     └────────────────────────────┬─────────────────────────────┘
                                  │ Ambang Batas: Skor >= 85 Poin
                                  ▼
     ┌──────────────────────────────────────────────────────────┐
     │ TAHAP 4: ATR DYNAMIC RISK-REWARD & POSITION SIZING FILTER│
     │ Validasi SL dinamis (1.5x ATR) & TP (3.0x ATR) -> R:R>=2 │
     └────────────────────────────┬─────────────────────────────┘
                                  │ Setup Siap Eksekusi
                                  ▼
     ┌──────────────────────────────────────────────────────────┐
     │ TAHAP 5: CLIENT-SIDE UI INTERACTIVE FILTERS & SEARCH     │
     │ Filter Cepat: Semua, Ultra (>=90%), VCP Ready, RS >= 85  │
     └──────────────────────────────────────────────────────────┘
```

---

## 2. Tahap 1: Top-Down Market Regime Filter (Macro Gatekeeper)

Statistik Wall Street membuktikan bahwa **$\approx 75\%$ pergerakan saham searah dengan indeks acuan**. Oleh karena itu, Tahap 1 bertindak sebagai saklar otomatis (*system kill-switch*) sebelum modal dialokasikan.

### Parameter yang Dipantau:
1. **$P_{\text{SPY}}$**: Harga ETF SPDR S&P 500 Trust terhadap $\text{EMA}_{20}$ dan $\text{SMA}_{50}$.
2. **$P_{\text{QQQ}}$**: Harga Invesco QQQ Trust terhadap tren rata-rata bergerak.
3. **$\text{VIX}$**: CBOE Volatility Index (indikator ketakutan pasar).

### Matriks Keputusan Status Pasar:

| Status Pasar | Kondisi Matematis | Kebijakan Sistem / Aksi Modal |
| :--- | :--- | :--- |
| **RISK-ON (Lampu Hijau)** | $P_{\text{SPY}} > \text{EMA}_{20} > \text{SMA}_{50} \quad \text{dan} \quad \text{VIX} < 18.0$ | **Alokasi 100%**. Prioritaskan pola *High Momentum Breakout* dan VCP agresif. |
| **NEUTRAL / CHOPPY (Lampu Kuning)** | $\text{SMA}_{50} < P_{\text{SPY}} < \text{EMA}_{20} \quad \text{atau} \quad 18.0 \le \text{VIX} \le 23.0$ | **Alokasi Maksimal 50%**. Hindari *breakout*, hanya izinkan *Pullback to Key Support* (EMA 50 / Trendline). |
| **RISK-OFF / BEAR (Lampu Merah)** | $P_{\text{SPY}} < \text{SMA}_{50} \quad \text{atau} \quad \text{VIX} > 23.0$ | **Cash Preservation Mode (Alokasi 0%)**. Blokir seluruh rekomendasi pembelian baru. |

---

## 3. Tahap 2: Earnings Blackout Guard (Event Risk Shield)

Salah satu celah terbesar dalam analisis teknikal murni adalah risiko rilis laporan keuangan kuartalan (*earnings report*). Lonjakan volatilitas (*earnings gap-down*) sebesar $-10\%$ hingga $-25\%$ dalam semalam tidak dapat dilindungi oleh Stop Loss harian biasa.

### Aturan Diskualifikasi Otomatis (Hard Stop):

Misalkan $t_{\text{earnings}}$ adalah jumlah hari bursa menuju jadwal pengumuman laba emiten:

$$
\text{Status Blackout} = 
\begin{cases} 
\text{BLOCKED (Blackout Aktif)}, & \text{jika } t_{\text{earnings}} \le 7 \\
\text{MONITORED (Waspada)}, & \text{jika } 8 \le t_{\text{earnings}} \le 14 \\
\text{SAFE (Aman)}, & \text{jika } t_{\text{earnings}} > 14 
\end{cases}
$$

### Konsekuensi Algoritmik jika $t_{\text{earnings}} \le 7$:
1. **Penalti Skor:** Total skor konfluensi dipangkas sebesar $30\%$:
   $$\text{Skor}_{\text{final}} = \lfloor \text{Skor}_{\text{murni}} \times 0.70 \rfloor$$
2. **Kunci Kategori:** Label probabilitas otomatis dialihkan menjadi `EARNINGS BLACKOUT` tanpa memandang kekuatan pola teknikal.
3. **Peringatan Antarmuka:** Ticker ditandai dengan badge peringatan merah berkedip (*pulsing badge*).

---

## 4. Tahap 3: 5-Pillar Multi-Factor Scoring Engine

Sistem mengaudit setiap saham yang lolos Tahap 2 menggunakan matriks kuantitatif 100 Poin yang terbagi ke dalam lima pilar:

$$\text{Total Skor} = S_{\text{Macro}} + S_{\text{RS}} + S_{\text{Tech}} + S_{\text{Fund}} + S_{\text{Flow}}$$

```
┌────────────────────────────────────────────────────────────────────────┐
│               DISTRIBUSI SKOR KONFLUENSI 5-PILAR (100 POIN)           │
├────────────────────────────┬──────────┬────────────────────────────────┤
│ Pilar                      │ Bobot    │ Fokus Utama                    │
├────────────────────────────┼──────────┼────────────────────────────────┤
│ 1. Macro & Market Regime   │ 15 Poin  │ Tren Indeks SPY/QQQ & VIX      │
│ 2. Relative Strength (RS)  │ 15 Poin  │ Mansfield RS vs S&P 500        │
│ 3. Struktur Teknikal & VCP │ 25 Poin  │ Volatility Contraction & VDU   │
│ 4. Katalis Fundamental     │ 25 Poin  │ Konsensus Analis & Laba/EPS    │
│ 5. Aliran Smart Money      │ 20 Poin  │ Put/Call Ratio & Opsi Derivatif│
└────────────────────────────┴──────────┴────────────────────────────────┘
```

### Rincian Sub-Kriteria Setiap Pilar:

#### Pilar 1: Macro & Regime Alignment (Maksimal 15 Poin)
* Status SPY & QQQ berada di atas $\text{EMA}_{20}$ & $\text{SMA}_{50}$ (10 Poin).
* Volatilitas VIX $< 20$ (5 Poin).

#### Pilar 2: Mansfield Relative Strength (RS vs SPY) (Maksimal 15 Poin)
Mengukur ketahanan relatif saham terhadap pasar acuan:

$$BP(t) = \frac{P_{\text{Stock}}(t)}{P_{\text{SPY}}(t)}$$

$$\text{Mansfield RS}(t) = \left( \frac{BP(t)}{\text{SMA}_{50}(BP(t))} - 1 \right) \times 100$$

* $\text{RS Rating} \ge 90$: Diberikan **15 Poin** (*True Market Leader*).
* $85 \le \text{RS Rating} < 90$: Diberikan **12 Poin**.
* $80 \le \text{RS Rating} < 85$: Diberikan **10 Poin**.
* $\text{RS Rating} < 80$: Diberikan $\le 8$ Poin.

#### Pilar 3: Struktur Teknikal & Minervini VCP (Maksimal 25 Poin)
* **Karakteristik VCP (Volatility Contraction Pattern):** Adanya siklus kontraksi rentang harga yang mengecil secara simetris:
  $$T_1 (\approx 10\%-18\%) \longrightarrow T_2 (\approx 5\%-9\%) \longrightarrow T_3 (\approx 2\%-4\%)$$
* **Volume Dry-Up (VDU):** Pada dasar kontraksi terakhir ($T_3$), volume transaksi harian wajib mengering di bawah $50\%$ rata-rata 20 hari:
  $$\text{Volume} < 0.5 \times \text{SMA}_{20}(\text{Volume})$$
* **Multi-Timeframe (MTF) Weekly Alignment:** Harga saham di grafik mingguan berada di atas $\text{SMA}_{30\text{-week}}$ (ekuivalen $\text{SMA}_{200\text{-day}}$) dengan kemiringan (*slope*) positif.
* Pemenuhan seluruh aspek teknikal di atas memberikan skor penuh **23–25 Poin**.

#### Pilar 4: Katalis Fundamental (Maksimal 25 Poin)
* Konsensus Wall Street "Strong Buy" atau "Buy" (10 Poin).
* Target harga rata-rata analis minimal $+15\%$ di atas harga saat ini (8 Poin).
* Rekam jejak *EPS Surprise* kuartalan positif mengalahkan konsensus (7 Poin).

#### Pilar 5: Aliran Smart Money & Opsi Derivatif (Maksimal 20 Poin)
* Rasio Volume Transaksi Put/Call ($\text{PCR}$) di bursa opsi:
  $$\text{PCR} = \frac{\text{Volume Opsi Put}}{\text{Volume Opsi Call}} < 0.45 \quad \implies \quad \text{Dominasi Bullish Institusi}$$
* Deteksi transaksi blok institusi (*Unusual Call Sweeps*).
* Zero *Insider Divestment* (ketiadaan penjualan saham oleh dewan direksi dalam 90 hari terakhir).
* Skor maksimum: **20 Poin**.

---

## 5. Tahap 4: ATR Dynamic Risk-Reward & Volatility Filter

Setelah skor konfluensi dihitung, saham harus melalui filter kelayakan matematis berbasis volatilitas riil. AlphaSwing US menyediakan dua mode perhitungan:

### Perbandingan Mode Level:

| Komponen | Mode Dinamis (ATR-14) — *Default* | Mode Statis (Fixed %) |
| :--- | :--- | :--- |
| **Metode Ukur** | $\text{ATR}_{14} = \text{RMA}(\text{TR}, 14)$ | Persentase Kaku |
| **Stop Loss (SL)** | $\text{Price} - (1.5 \times \text{ATR}_{14})$ | $\text{Price} \times 0.95$ ($-5\%$) |
| **Take Profit (TP)** | $\text{Price} + (3.0 \times \text{ATR}_{14})$ | $\text{Price} \times 1.15$ ($+15\%$) |
| **Zona Beli (Buy Area)** | $[\text{Price} - (0.5 \times \text{ATR}_{14}),\; \text{Price}]$ | $[0.985 \times \text{Price},\; \text{Price}]$ |

### Formula Position Sizing (Proteksi Modal):
Untuk menjaga risiko modal terukur pada batas toleransi (default $1\%$ per transaksi):

$$\text{Batas Kerugian Maksimal (\$) } (D_{\text{risk}}) = \text{Total Modal Akun} \times \left( \frac{\text{Persentase Risiko}}{100} \right)$$

$$\text{Risk per Lembar} (R_{\text{share}}) = \text{Entry Price} - \text{Stop Loss}$$

$$\text{Jumlah Lembar Saham Aman} (N) = \left\lfloor \frac{D_{\text{risk}}}{R_{\text{share}}} \right\rfloor$$

$$\text{Rasio Risk : Reward} = \frac{\text{Target Price} - \text{Entry Price}}{\text{Entry Price} - \text{Stop Loss}}$$

### Kriteria Kelayakan (*Gatekeeper Rule*):
* **SETUP LAYAK:** Jika $\text{Rasio R:R} \ge 1 : 2.0$ (Mode ATR) atau $\ge 1 : 2.5$ (Mode Fixed).
* **SETUP KURANG LAYAK / DITOLAK:** Jika $\text{Rasio R:R} < 2.0$. Sistem menampilkan status peringatan merah pada kalkulator.

---

## 6. Tahap 5: Client-Side Interactive Filtering & Search Logic

Pada antarmuka web (`index.html`), logika filtering diimplementasikan melalui eksekusi JavaScript terpadu pada fungsi `renderStocksTable()`.

### Algoritma Evaluasi Multi-Kondisi:

```javascript
// Cuplikan pseudocode algoritma filtering pada renderStocksTable()
const filtered = STOCKS_DATA.filter(stock => {
  const totalScore = calculateTotalScore(stock);
  const isBlackout = stock.earningsDaysAway <= 7;

  // 1. Evaluasi Filter Kategori (Pill Buttons)
  let matchesCategory = true;
  if (currentFilter === 'ULTRA') {
    matchesCategory = (totalScore >= 90) && !isBlackout;
  } else if (currentFilter === 'VCP') {
    matchesCategory = stock.vcpStatus.includes("Ready");
  } else if (currentFilter === 'RS_HIGH') {
    matchesCategory = stock.rsRating >= 85;
  }

  // 2. Evaluasi Filter Pencarian Cepat (Case-Insensitive Substring)
  const q = searchQuery.toLowerCase().trim();
  const matchesSearch = (q === '') || 
    stock.ticker.toLowerCase().includes(q) ||
    stock.name.toLowerCase().includes(q) ||
    stock.sector.toLowerCase().includes(q);

  // 3. Konfluensi Gabungan
  return matchesCategory && matchesSearch;
});
```

### Logika Penyortiran (*Sorting Priority*):
Hasil penyaringan selalu diurutkan secara menurun (*descending*) berdasarkan $\text{Total Skor Konfluensi}$:
$$\text{Sorted List} = \text{OrderByDescending}(S_{\text{Total}})$$
Saham dengan konfluensi paling sempurna ($\ge 90\%$) otomatis menempati posisi teratas tabel.

---

## 7. Matriks Klasifikasi Peluang Akhir

Berdasarkan keseluruhan proses di atas, setiap saham dikategorikan ke dalam salah satu kelas berikut:

| Kategori Peluang | Syarat Skor & Kondisi | Warna Badge | Tindakan Trader |
| :--- | :--- | :--- | :--- |
| **Ultra High Probability** | Skor $\ge 90$ Poin & Bebas Blackout | Hijau Emerald Glow | **Prioritas Eksekusi Utama**. Siapkan *limit order* di Buy Zone. |
| **High Confluence** | Skor $85 - 89$ Poin & Bebas Blackout | Cyan | **Prioritas Kedua**. Pantau penembusan volume pada pivot breakout. |
| **Moderate Swing** | Skor $< 85$ Poin | Abu-abu Slate | **Watchlist Cadangan**. Belum memenuhi standar konfluensi institusi. |
| **EARNINGS BLACKOUT** | Jadwal Earnings $\le 7$ Hari Bursa | Amber / Merah Pulsing | **DILARANG BELI (BLOCKED)**. Tunggu rilis laba tuntas (Strategi PEAD). |