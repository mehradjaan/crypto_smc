"""Classic technical indicators + divergences."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    gain = d.clip(lower=0.0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-d.clip(upper=0.0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = _ema(close, 12) - _ema(close, 26)
    signal = line.ewm(span=9, adjust=False).mean()
    return line, signal, line - signal


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev).abs(),
            (df["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = atr(df, n)  # smoothed TR already; use raw TR for Wilder
    prev = df["close"].shift(1)
    tr_raw = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev).abs(),
            (df["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_w = tr_raw.ewm(alpha=1 / n, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / atr_w
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / atr_w
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def stochastic(df: pd.DataFrame, k: int = 14, d: int = 3) -> tuple[pd.Series, pd.Series]:
    low_n = df["low"].rolling(k).min()
    high_n = df["high"].rolling(k).max()
    k_line = 100 * (df["close"] - low_n) / (high_n - low_n).replace(0, np.nan)
    d_line = k_line.rolling(d).mean()
    return k_line, d_line


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=0)
    return mid + k * sd, mid, mid - k * sd


def vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan)
    return (tp * vol).cumsum() / vol.cumsum()


@dataclass
class TASnapshot:
    rsi: float | None
    rsi_state: str
    macd_line: float | None
    macd_signal: float | None
    macd_hist: float | None
    macd_cross: str
    ema9: float | None
    ema21: float | None
    ema50: float | None
    ema200: float | None
    ema_stack: str
    atr: float | None
    atr_pct: float | None
    adx: float | None
    trend_strength: str
    stoch_k: float | None
    stoch_d: float | None
    bb_upper: float | None
    bb_mid: float | None
    bb_lower: float | None
    bb_position: str
    vwap: float | None
    vs_vwap: str
    volume_ratio: float | None
    volume_state: str
    last_close: float
    divergence: str | None
    notes: list[str]


def _f(x) -> float | None:
    try:
        v = float(x)
        if not np.isfinite(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def detect_rsi_divergence(df: pd.DataFrame, rsi_s: pd.Series, lookback: int = 80) -> str | None:
    if len(df) < 30:
        return None
    sl = df.tail(lookback).copy()
    sl["rsi"] = rsi_s.reindex(sl.index)
    highs = []
    lows = []
    h = sl["high"].values
    l = sl["low"].values
    r = sl["rsi"].values
    for i in range(3, len(sl) - 3):
        if h[i] >= max(h[i - 3 : i + 4]) and np.isfinite(r[i]):
            highs.append((i, h[i], r[i]))
        if l[i] <= min(l[i - 3 : i + 4]) and np.isfinite(r[i]):
            lows.append((i, l[i], r[i]))
    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        if b[1] > a[1] * 1.0005 and b[2] < a[2] - 1.5:
            return "bearish"
        if b[1] < a[1] * 0.9995 and b[2] > a[2] + 1.5:
            return "hidden_bearish"
    if len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        if b[1] < a[1] * 0.9995 and b[2] > a[2] + 1.5:
            return "bullish"
        if b[1] > a[1] * 1.0005 and b[2] < a[2] - 1.5:
            return "hidden_bullish"
    return None


def compute_ta(df: pd.DataFrame) -> tuple[TASnapshot, dict[str, list]]:
    close = df["close"]
    last = float(close.iloc[-1])
    ema9 = _ema(close, 9)
    ema21 = _ema(close, 21)
    ema50 = _ema(close, 50)
    ema200 = _ema(close, 200) if len(df) >= 210 else pd.Series(np.nan, index=df.index)
    rsi_s = rsi(close)
    macd_l, macd_s, macd_h = macd(close)
    atr_s = atr(df)
    adx_s = adx(df)
    k_s, d_s = stochastic(df)
    bb_u, bb_m, bb_l = bollinger(close)
    vwap_s = vwap(df)

    e9, e21, e50, e200 = _f(ema9.iloc[-1]), _f(ema21.iloc[-1]), _f(ema50.iloc[-1]), _f(ema200.iloc[-1])
    stack = "mixed"
    if e9 and e21 and e50:
        if e9 > e21 > e50 and (e200 is None or e50 > e200):
            stack = "bullish"
        elif e9 < e21 < e50 and (e200 is None or e50 < e200):
            stack = "bearish"

    r = _f(rsi_s.iloc[-1])
    if r is None:
        rsi_state = "n/a"
    elif r >= 70:
        rsi_state = "overbought"
    elif r <= 30:
        rsi_state = "oversold"
    elif r >= 55:
        rsi_state = "bullish"
    elif r <= 45:
        rsi_state = "bearish"
    else:
        rsi_state = "neutral"

    mh, ml, ms = _f(macd_h.iloc[-1]), _f(macd_l.iloc[-1]), _f(macd_s.iloc[-1])
    macd_cross = "neutral"
    if ml is not None and ms is not None:
        prev_l, prev_s = _f(macd_l.iloc[-2]), _f(macd_s.iloc[-2])
        if prev_l is not None and prev_s is not None:
            if prev_l <= prev_s and ml > ms:
                macd_cross = "bullish_cross"
            elif prev_l >= prev_s and ml < ms:
                macd_cross = "bearish_cross"
            elif ml > ms:
                macd_cross = "bullish"
            else:
                macd_cross = "bearish"

    adx_v = _f(adx_s.iloc[-1])
    if adx_v is None:
        strength = "n/a"
    elif adx_v >= 40:
        strength = "very_strong"
    elif adx_v >= 25:
        strength = "strong"
    elif adx_v >= 18:
        strength = "moderate"
    else:
        strength = "weak_range"

    bu, bm, bl = _f(bb_u.iloc[-1]), _f(bb_m.iloc[-1]), _f(bb_l.iloc[-1])
    bb_pos = "mid"
    if bu and bl:
        if last >= bu:
            bb_pos = "above_upper"
        elif last <= bl:
            bb_pos = "below_lower"
        elif bm and last > bm:
            bb_pos = "upper_half"
        else:
            bb_pos = "lower_half"

    vw = _f(vwap_s.iloc[-1])
    vs_vwap = "n/a" if vw is None else ("above" if last > vw else "below")

    vol_ma = df["volume"].rolling(20).mean()
    vr = _f(df["volume"].iloc[-1] / vol_ma.iloc[-1]) if _f(vol_ma.iloc[-1]) else None
    if vr is None:
        vol_state = "n/a"
    elif vr >= 2:
        vol_state = "climax"
    elif vr >= 1.3:
        vol_state = "high"
    elif vr <= 0.6:
        vol_state = "low"
    else:
        vol_state = "normal"

    atr_v = _f(atr_s.iloc[-1])
    atr_pct = (atr_v / last * 100) if atr_v and last else None

    div = detect_rsi_divergence(df, rsi_s)

    notes = []
    if stack == "bullish":
        notes.append("چینش میانگین‌ها صعودی است (EMA۹ > ۲۱ > ۵۰).")
    elif stack == "bearish":
        notes.append("چینش میانگین‌ها نزولی است (EMA۹ < ۲۱ < ۵۰).")
    if rsi_state == "overbought":
        notes.append("RSI در اشباع خرید است؛ احتمال اصلاح یا ادامه با مومنتوم.")
    elif rsi_state == "oversold":
        notes.append("RSI در اشباع فروش است؛ احتمال برگشت کوتاه‌مدت.")
    if macd_cross.endswith("cross"):
        notes.append("کراس تازه‌ی MACD دیده می‌شود.")
    if div == "bullish":
        notes.append("واگرایی مثبت RSI (کف پایین‌تر قیمت، RSI بالاتر).")
    elif div == "bearish":
        notes.append("واگرایی منفی RSI (سقف بالاتر قیمت، RSI پایین‌تر).")
    if strength in ("weak_range",):
        notes.append("ADX ضعیف است؛ بازار بیشتر رنج است تا ترند.")
    elif strength in ("strong", "very_strong"):
        notes.append("ADX از قدرت روند حمایت می‌کند.")

    snap = TASnapshot(
        rsi=r,
        rsi_state=rsi_state,
        macd_line=ml,
        macd_signal=ms,
        macd_hist=mh,
        macd_cross=macd_cross,
        ema9=e9,
        ema21=e21,
        ema50=e50,
        ema200=e200,
        ema_stack=stack,
        atr=atr_v,
        atr_pct=atr_pct,
        adx=adx_v,
        trend_strength=strength,
        stoch_k=_f(k_s.iloc[-1]),
        stoch_d=_f(d_s.iloc[-1]),
        bb_upper=bu,
        bb_mid=bm,
        bb_lower=bl,
        bb_position=bb_pos,
        vwap=vw,
        vs_vwap=vs_vwap,
        volume_ratio=vr,
        volume_state=vol_state,
        last_close=last,
        divergence=div,
        notes=notes,
    )

    series = {
        "ema21": [None if not np.isfinite(v) else float(v) for v in ema21.tail(250)],
        "ema50": [None if not np.isfinite(v) else float(v) for v in ema50.tail(250)],
    }
    return snap, series
