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
