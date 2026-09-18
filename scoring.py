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
        return ((pure * 70) // 100, True)
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
