"""Smart Money Concepts: structure, FVG, order blocks, liquidity, premium/discount."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from .ta import atr as calc_atr


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _f(x) -> float | None:
    try:
        v = float(x)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


@dataclass
class Swing:
    index: int
    time: int
    price: float
    kind: str  # high | low


@dataclass
class StructureEvent:
    index: int
    time: int
    price: float
    kind: str  # BOS | CHoCH
    direction: str
    broken_level: float


@dataclass
class Zone:
    start_index: int
    time: int
    top: float
    bottom: float
    direction: str
    kind: str  # fvg | ob | breaker
    status: str  # fresh | tapped | filled | invalidated
    strength: float
    ce: float  # 50% (consequent encroachment)


@dataclass
class Sweep:
    index: int
    time: int
    direction: str  # ssl | bsl  (sell-side / buy-side taken)
    level: float
    close: float


@dataclass
class SMCResult:
    trend: str
    structure_label: str
    last_event: dict | None
    events: list[dict]
    swings: list[dict]
    fvgs: list[dict]
    order_blocks: list[dict]
    breakers: list[dict]
    equal_highs: list[dict]
    equal_lows: list[dict]
    liquidity: dict
    sweeps: list[dict]
    dealing_range: dict
    premium_discount: str
    ote: dict
    nearby: dict
    displacement: dict
    session: str
    notes: list[str] = field(default_factory=list)


def find_swings(high: np.ndarray, low: np.ndarray, n: int = 5) -> tuple[list[int], list[int]]:
    length = len(high)
    sh, sl = [], []
    if length < n * 2 + 3:
        return sh, sl
    for i in range(n, length - n):
        left_h = high[i - n : i]
        right_h = high[i + 1 : i + n + 1]
        left_l = low[i - n : i]
        right_l = low[i + 1 : i + n + 1]
        if high[i] > left_h.max() and high[i] >= right_h.max():
            sh.append(i)
        if low[i] < left_l.min() and low[i] <= right_l.min():
            sl.append(i)
    return sh, sl


def _detect_structure(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    times: np.ndarray,
    swing_n: int,
) -> tuple[list[StructureEvent], list[Swing], int]:
    sh_idx, sl_idx = find_swings(high, low, swing_n)
    swings: list[Swing] = []
    for i in sh_idx:
        swings.append(Swing(i, int(times[i]), float(high[i]), "high"))
    for i in sl_idx:
        swings.append(Swing(i, int(times[i]), float(low[i]), "low"))
    swings.sort(key=lambda s: s.index)

    confirmations: list[tuple[int, str, int, float]] = []
    for i in sh_idx:
        confirmations.append((i + swing_n, "h", i, float(high[i])))
    for i in sl_idx:
        confirmations.append((i + swing_n, "l", i, float(low[i])))
    confirmations.sort()

    events: list[StructureEvent] = []
    trend = 0
    last_sh = last_sl = None  # (price, idx)
    si = 0
    n = len(close)
    for bar in range(n):
        while si < len(confirmations) and confirmations[si][0] <= bar:
            _, k, idx, price = confirmations[si]
            if k == "h":
                last_sh = (price, idx)
            else:
                last_sl = (price, idx)
            si += 1
        if last_sh is not None and close[bar] > last_sh[0]:
            kind = "BOS" if trend in (0, 1) else "CHoCH"
            if trend == 0:
                kind = "BOS"
            events.append(
                StructureEvent(
                    index=bar,
                    time=int(times[bar]),
                    price=float(close[bar]),
                    kind=kind,
                    direction="bullish",
                    broken_level=float(last_sh[0]),
                )
            )
            trend = 1
            last_sh = None
        elif last_sl is not None and close[bar] < last_sl[0]:
            kind = "BOS" if trend in (0, -1) else "CHoCH"
            if trend == 0:
                kind = "BOS"
            events.append(
                StructureEvent(
                    index=bar,
                    time=int(times[bar]),
                    price=float(close[bar]),
                    kind=kind,
                    direction="bearish",
                    broken_level=float(last_sl[0]),
                )
            )
            trend = -1
            last_sl = None
    return events, swings, trend


def _structure_label(swings: list[Swing]) -> str:
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return "نامشخص"
    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    if hh and hl:
        return "HH / HL (صعودی)"
    if (not hh) and (not hl):
        return "LH / LL (نزولی)"
    if hh and not hl:
        return "HH / LL (گسترشی / رنج)"
    return "LH / HL (فشرده / رنج)"


def _last_opposite(o, h, l, c, start: int, end: int, bullish_ob: bool) -> int | None:
    start = max(0, start)
    end = max(start + 1, end)
    for j in range(end - 1, start - 1, -1):
        if bullish_ob and c[j] < o[j]:
            return j
        if not bullish_ob and c[j] > o[j]:
            return j
    window_h = h[start:end]
    window_l = l[start:end]
    if len(window_l) == 0:
        return None
    if bullish_ob:
        return int(np.argmin(window_l)) + start
    return int(np.argmax(window_h)) + start


def _zone_status_ob(h, l, c, idx: int, top: float, bottom: float, bullish: bool) -> str:
    n = len(c)
    tapped = False
    for k in range(idx + 1, n):
        if bullish:
            if l[k] <= top:
                tapped = True
            if c[k] < bottom:
                return "invalidated"
        else:
            if h[k] >= bottom:
                tapped = True
            if c[k] > top:
                return "invalidated"
    return "tapped" if tapped else "fresh"


def _detect_obs(
    o, h, l, c, times, events: list[StructureEvent], swings: list[Swing], atr_v: np.ndarray
) -> tuple[list[Zone], list[Zone]]:
    obs: list[Zone] = []
    breakers: list[Zone] = []
    swing_lows = [s for s in swings if s.kind == "low"]
    swing_highs = [s for s in swings if s.kind == "high"]

    for ev in events:
        if ev.direction == "bullish":
            prev_lows = [s for s in swing_lows if s.index < ev.index]
            start = prev_lows[-1].index if prev_lows else max(0, ev.index - 20)
            j = _last_opposite(o, h, l, c, start, ev.index, bullish_ob=True)
            if j is None:
                continue
            top, bottom = float(h[j]), float(l[j])
            status = _zone_status_ob(h, l, c, j, top, bottom, True)
            move = float(c[ev.index] - bottom)
            a = float(atr_v[ev.index]) if np.isfinite(atr_v[ev.index]) else move
            strength = min(1.0, (move / (a * 3 + 1e-12)))
            if ev.kind == "CHoCH":
                strength = min(1.0, strength + 0.2)
            z = Zone(j, int(times[j]), top, bottom, "bullish", "ob", status, strength, (top + bottom) / 2)
            obs.append(z)
            if status == "invalidated":
                breakers.append(
                    Zone(j, int(times[j]), top, bottom, "bearish", "breaker", "fresh", strength, (top + bottom) / 2)
                )
        else:
            prev_highs = [s for s in swing_highs if s.index < ev.index]
            start = prev_highs[-1].index if prev_highs else max(0, ev.index - 20)
            j = _last_opposite(o, h, l, c, start, ev.index, bullish_ob=False)
            if j is None:
                continue
            top, bottom = float(h[j]), float(l[j])
            status = _zone_status_ob(h, l, c, j, top, bottom, False)
            move = float(top - c[ev.index])
            a = float(atr_v[ev.index]) if np.isfinite(atr_v[ev.index]) else move
            strength = min(1.0, (move / (a * 3 + 1e-12)))
            if ev.kind == "CHoCH":
                strength = min(1.0, strength + 0.2)
            z = Zone(j, int(times[j]), top, bottom, "bearish", "ob", status, strength, (top + bottom) / 2)
            obs.append(z)
            if status == "invalidated":
                breakers.append(
                    Zone(j, int(times[j]), top, bottom, "bullish", "breaker", "fresh", strength, (top + bottom) / 2)
                )

    # keep the most recent unique zones (by index)
    def _dedup(items: list[Zone]) -> list[Zone]:
        seen = set()
        out = []
        for z in sorted(items, key=lambda x: x.start_index):
            key = (z.start_index, z.direction, z.kind)
            if key in seen:
                continue
            seen.add(key)
            out.append(z)
        return out[-8:]

    return _dedup(obs), _dedup(breakers)


def _detect_fvg(h, l, c, times, atr_v: np.ndarray, min_pct: float) -> list[Zone]:
    n = len(c)
    zones: list[Zone] = []
    for i in range(2, n):
        # bullish FVG: gap between candle i-2 high and candle i low
        if l[i] > h[i - 2]:
            top, bottom = float(l[i]), float(h[i - 2])
            gap = top - bottom
            px = float(c[i])
            a = float(atr_v[i]) if np.isfinite(atr_v[i]) else 0.0
            if gap < max(px * min_pct, a * 0.12):
                continue
            status = "fresh"
            ce = (top + bottom) / 2
            for k in range(i + 1, n):
                if l[k] <= bottom:
                    status = "filled"
                    break
                if l[k] <= ce:
                    status = "tapped"
            strength = min(1.0, gap / (a + 1e-12) / 2)
            zones.append(Zone(i - 1, int(times[i - 1]), top, bottom, "bullish", "fvg", status, strength, ce))
        # bearish FVG
        if h[i] < l[i - 2]:
            top, bottom = float(l[i - 2]), float(h[i])
            gap = top - bottom
            px = float(c[i])
            a = float(atr_v[i]) if np.isfinite(atr_v[i]) else 0.0
            if gap < max(px * min_pct, a * 0.12):
                continue
            status = "fresh"
            ce = (top + bottom) / 2
            for k in range(i + 1, n):
                if h[k] >= top:
                    status = "filled"
                    break
                if h[k] >= ce:
                    status = "tapped"
            strength = min(1.0, gap / (a + 1e-12) / 2)
            zones.append(Zone(i - 1, int(times[i - 1]), top, bottom, "bearish", "fvg", status, strength, ce))

    # keep unfilled + last few filled
    live = [z for z in zones if z.status != "filled"]
    filled = [z for z in zones if z.status == "filled"][-4:]
    return (live + filled)[-10:]


def _equal_levels(swings: list[Swing], kind: str, atr_last: float, price: float) -> list[dict]:
    pts = [s for s in swings if s.kind == kind]
    if len(pts) < 2:
        return []
    tol = max(price * 0.0012, atr_last * 0.18)
    used = set()
    clusters = []
    for i, a in enumerate(pts):
        if i in used:
            continue
        group = [a]
        used.add(i)
        for j, b in enumerate(pts):
            if j in used:
                continue
            if abs(a.price - b.price) <= tol:
                group.append(b)
                used.add(j)
        if len(group) >= 2:
            avg = sum(g.price for g in group) / len(group)
            clusters.append(
                {
                    "price": avg,
                    "count": len(group),
                    "times": [_iso(g.time) for g in group[-3:]],
                    "kind": "EQH" if kind == "high" else "EQL",
                }
            )
    return clusters[-4:]


def _sweeps(h, l, c, times, swings: list[Swing], lookback: int = 40) -> list[Sweep]:
    n = len(c)
    start = max(0, n - lookback)
    out: list[Sweep] = []
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    for i in range(start, n):
        recent_h = [s for s in highs if s.index < i]
        recent_l = [s for s in lows if s.index < i]
        if recent_h:
            lvl = recent_h[-1].price
            if h[i] > lvl and c[i] < lvl:
                out.append(Sweep(i, int(times[i]), "bsl", float(lvl), float(c[i])))
        if recent_l:
            lvl = recent_l[-1].price
            if l[i] < lvl and c[i] > lvl:
                out.append(Sweep(i, int(times[i]), "ssl", float(lvl), float(c[i])))
    # unique-ish last few
    return out[-6:]


def _dealing_range(swings: list[Swing], last: float) -> dict:
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    if not highs or not lows:
        return {}
    # most recent significant pair: last swing high & last swing low
    sh = highs[-1]
    sl = lows[-1]
    top, bot = max(sh.price, sl.price), min(sh.price, sl.price)
    # if last high is older than last low, still use both
    if top <= bot:
        return {}
    rng = top - bot
    pos = (last - bot) / rng
    fibs = {
        "0": bot,
        "0.236": bot + rng * 0.236,
        "0.382": bot + rng * 0.382,
        "0.5": bot + rng * 0.5,
        "0.618": bot + rng * 0.618,
        "0.705": bot + rng * 0.705,
        "0.786": bot + rng * 0.786,
        "1": top,
    }
    # OTE depends on direction of the range (from low to high = bullish dealing)
    bullish_range = sl.index < sh.index
    if bullish_range:
        ote_low, ote_high = fibs["0.618"], fibs["0.786"]
        # buy OTE is discount of bullish range: 0.618-0.786 measured from high
        ote_low, ote_high = bot + rng * (1 - 0.786), bot + rng * (1 - 0.618)
    else:
        ote_low, ote_high = bot + rng * 0.618, bot + rng * 0.786

    if pos > 1:
        pd = "premium"
    elif pos < 0:
        pd = "discount"
    elif pos >= 0.5:
        pd = "premium"
    else:
        pd = "discount"
    if 0.47 <= pos <= 0.53:
        pd = "equilibrium"

    return {
        "high": sh.price,
        "low": sl.price,
        "high_time": _iso(sh.time),
        "low_time": _iso(sl.time),
        "equilibrium": (top + bot) / 2,
        "position": pos,
        "premium_discount": pd,
        "fib": fibs,
        "ote": {"low": ote_low, "high": ote_high, "in_ote": ote_low <= last <= ote_high},
        "bullish_range": bullish_range,
    }


def _session_name(ts_ms: int) -> str:
    hour = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).hour
    tags = []
    if 0 <= hour < 8:
        tags.append("آسیا")
    if 7 <= hour < 16:
        tags.append("لندن")
    if 12 <= hour < 21:
        tags.append("نیویورک")
    if not tags:
        tags.append("آسیا (اوایل)")
    overlap = []
    if 7 <= hour < 8:
        overlap.append("هم‌پوشانی آسیا/لندن")
    if 12 <= hour < 16:
        overlap.append("هم‌پوشانی لندن/نیویورک (فعال‌ترین)")
    return "، ".join(tags) + ((" — " + overlap[0]) if overlap else "")


def _zone_dict(z: Zone) -> dict[str, Any]:
    d = asdict(z)
    d["time_label"] = _iso(z.time)
    d["mid"] = (z.top + z.bottom) / 2
    return d


def _nearest_zones(last: float, atr_last: float, fvgs: list[Zone], obs: list[Zone]) -> dict:
    def dist(z: Zone) -> float:
        if z.bottom <= last <= z.top:
            return 0.0
        if last < z.bottom:
            return z.bottom - last
        return last - z.top

    def pack(z: Zone | None) -> dict | None:
        if z is None:
            return None
        return {
            **_zone_dict(z),
            "distance": dist(z),
            "distance_atr": dist(z) / atr_last if atr_last else None,
            "inside": dist(z) == 0.0,
        }

    live_fvg = [z for z in fvgs if z.status != "filled"]
    live_ob = [z for z in obs if z.status != "invalidated"]
    bull_fvg = min([z for z in live_fvg if z.direction == "bullish"], key=dist, default=None)
    bear_fvg = min([z for z in live_fvg if z.direction == "bearish"], key=dist, default=None)
    bull_ob = min([z for z in live_ob if z.direction == "bullish"], key=dist, default=None)
    bear_ob = min([z for z in live_ob if z.direction == "bearish"], key=dist, default=None)
    return {
        "bullish_fvg": pack(bull_fvg),
        "bearish_fvg": pack(bear_fvg),
        "bullish_ob": pack(bull_ob),
        "bearish_ob": pack(bear_ob),
    }


def analyze_smc(df: pd.DataFrame, swing_n: int = 5, fvg_min_pct: float = 0.0004) -> SMCResult:
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    times = df["time"].to_numpy(dtype=np.int64)
    atr_s = calc_atr(df).to_numpy(dtype=float)
    last = float(c[-1])
    atr_last = float(atr_s[-1]) if np.isfinite(atr_s[-1]) else last * 0.01

    events, swings, trend_i = _detect_structure(h, l, c, times, swing_n)
    obs, breakers = _detect_obs(o, h, l, c, times, events, swings, atr_s)
    fvgs = _detect_fvg(h, l, c, times, atr_s, fvg_min_pct)
    eqh = _equal_levels(swings, "high", atr_last, last)
    eql = _equal_levels(swings, "low", atr_last, last)
    sweeps = _sweeps(h, l, c, times, swings)
    dr = _dealing_range(swings, last)

    trend = "bullish" if trend_i == 1 else "bearish" if trend_i == -1 else "neutral"
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    bsl = [{"price": s.price, "time": _iso(s.time)} for s in highs[-3:]]
    ssl = [{"price": s.price, "time": _iso(s.time)} for s in lows[-3:]]

    # displacement: last 8 candles
    bodies = np.abs(c - o)
    disp = {"present": False, "direction": "none", "bars": 0}
    run = 0
    run_dir = 0
    for i in range(len(c) - 8, len(c)):
        if i < 1:
            continue
        a = atr_s[i] if np.isfinite(atr_s[i]) else bodies[i]
        bull = c[i] > o[i] and bodies[i] >= 1.35 * a
        bear = c[i] < o[i] and bodies[i] >= 1.35 * a
        if bull:
            if run_dir == 1:
                run += 1
            else:
                run, run_dir = 1, 1
        elif bear:
            if run_dir == -1:
                run += 1
            else:
                run, run_dir = 1, -1
        else:
            run, run_dir = 0, 0
    if run >= 1:
        disp = {
            "present": True,
            "direction": "bullish" if run_dir == 1 else "bearish",
            "bars": run,
        }

    last_event = None
    if events:
        ev = events[-1]
        last_event = {
            "kind": ev.kind,
            "direction": ev.direction,
            "price": ev.price,
            "broken_level": ev.broken_level,
            "time": _iso(ev.time),
            "bars_ago": int(len(c) - 1 - ev.index),
        }

    notes: list[str] = []
    if last_event:
        fa = "صعودی" if last_event["direction"] == "bullish" else "نزولی"
        notes.append(
            f"آخرین رویداد ساختار: {last_event['kind']} {fa} "
            f"({last_event['bars_ago']} کندل پیش، سطح {last_event['broken_level']:.6g})."
        )
    notes.append(f"برچسب سوئینگ‌ها: {_structure_label(swings)}.")
    if dr:
        pd_fa = {"premium": "پرمیوم", "discount": "دیسکانت", "equilibrium": "تعادل"}.get(
            dr.get("premium_discount", ""), dr.get("premium_discount", "")
        )
        notes.append(
            f"قیمت در ناحیهٔ {pd_fa} محدودهٔ معاملاتی "
            f"({dr['low']:.6g} – {dr['high']:.6g}) است."
        )
    live_ob = [z for z in obs if z.status == "fresh"]
    if live_ob:
        z = live_ob[-1]
        notes.append(
            f"اردر بلاک {('صعودی' if z.direction == 'bullish' else 'نزولی')} تازه: "
            f"{z.bottom:.6g} – {z.top:.6g}."
        )
    live_fvg = [z for z in fvgs if z.status == "fresh"]
    if live_fvg:
        z = live_fvg[-1]
        notes.append(
            f"FVG {('صعودی' if z.direction == 'bullish' else 'نزولی')} پرنشده: "
            f"{z.bottom:.6g} – {z.top:.6g}."
        )
    if sweeps:
        sw = sweeps[-1]
        if sw.direction == "ssl":
            notes.append("سوئیپ نقدینگی فروش (SSL) اخیراً رخ داده — می‌تواند سوخت حرکت صعودی باشد.")
        else:
            notes.append("سوئیپ نقدینگی خرید (BSL) اخیراً رخ داده — می‌تواند سوخت حرکت نزولی باشد.")
    if disp["present"]:
        notes.append(
            f"جابه‌جایی (Displacement) {('صعودی' if disp['direction']=='bullish' else 'نزولی')} "
            f"در {disp['bars']} کندل اخیر."
        )

    nearby = _nearest_zones(last, atr_last, fvgs, obs)

    return SMCResult(
        trend=trend,
        structure_label=_structure_label(swings),
        last_event=last_event,
        events=[
            {
                "index": e.index,
                "time": e.time,
                "time_label": _iso(e.time),
                "price": e.price,
                "kind": e.kind,
                "direction": e.direction,
                "broken_level": e.broken_level,
            }
            for e in events[-12:]
        ],
        swings=[
            {
                "index": s.index,
                "time": s.time,
                "time_label": _iso(s.time),
                "price": s.price,
                "kind": s.kind,
            }
            for s in swings[-24:]
        ],
        fvgs=[_zone_dict(z) for z in fvgs],
        order_blocks=[_zone_dict(z) for z in obs],
        breakers=[_zone_dict(z) for z in breakers],
        equal_highs=eqh,
        equal_lows=eql,
        liquidity={
            "buy_side": bsl,
            "sell_side": ssl,
            "nearest_bsl": bsl[-1]["price"] if bsl else None,
            "nearest_ssl": ssl[-1]["price"] if ssl else None,
        },
        sweeps=[
            {
                "index": s.index,
                "time": s.time,
                "time_label": _iso(s.time),
                "direction": s.direction,
                "level": s.level,
                "close": s.close,
            }
            for s in sweeps
        ],
        dealing_range=dr,
        premium_discount=dr.get("premium_discount", "n/a") if dr else "n/a",
        ote=dr.get("ote", {}) if dr else {},
        nearby=nearby,
        displacement=disp,
        session=_session_name(int(times[-1])),
        notes=notes,
    )
