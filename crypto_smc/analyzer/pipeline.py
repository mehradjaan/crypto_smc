"""End-to-end: parse query → fetch candles → TA + SMC → confluence report."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from .data import EXCHANGE_LABEL, DataError, load_market_cached
from .parse import parse_query
from .report import TF_META, TF_ORDER, confluence, narrative_tf, score_tf, ta_dict
from .smc import analyze_smc
from .ta import compute_ta


CHART_BARS = 220

SWING_N = {"1m": 8, "5m": 6, "15m": 5, "30m": 5, "1h": 5, "4h": 5}
FVG_MIN = {"1m": 0.00025, "5m": 0.0003, "15m": 0.00032, "30m": 0.00035, "1h": 0.0004, "4h": 0.00045}


def _clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if not math.isfinite(v) else v
    if isinstance(obj, (pd.Timestamp, datetime)):
        if isinstance(obj, pd.Timestamp):
            obj = obj.to_pydatetime()
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.isoformat()
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    return obj


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _chart_payload(df: pd.DataFrame, smc, ema_series: dict[str, list]) -> dict[str, Any]:
    tail = df.tail(CHART_BARS).reset_index(drop=True)
    candles = []
    for row in tail.itertuples(index=False):
        candles.append(
            {
                "t": _iso(int(row.time)),
                "o": float(row.open),
                "h": float(row.high),
                "l": float(row.low),
                "c": float(row.close),
                "v": float(row.volume) if row.volume == row.volume else 0.0,
            }
        )
    last_t = candles[-1]["t"]
    t0 = int(tail["time"].iloc[0])

    shapes = []
    for z in smc.fvgs:
        if z["status"] == "filled":
            continue
        color = "rgba(46,230,197,0.16)" if z["direction"] == "bullish" else "rgba(255,107,122,0.16)"
        line = "rgba(46,230,197,0.55)" if z["direction"] == "bullish" else "rgba(255,107,122,0.55)"
        shapes.append(
            {
                "type": "rect",
                "x0": _iso(int(z["time"])),
                "x1": last_t,
                "y0": z["bottom"],
                "y1": z["top"],
                "fill": color,
                "line": line,
                "label": f"FVG {z['direction']}",
            }
        )
    for z in smc.order_blocks:
        if z["status"] == "invalidated":
            continue
        color = "rgba(76,141,255,0.16)" if z["direction"] == "bullish" else "rgba(240,180,41,0.16)"
        line = "rgba(76,141,255,0.55)" if z["direction"] == "bullish" else "rgba(240,180,41,0.55)"
        shapes.append(
            {
                "type": "rect",
                "x0": _iso(int(z["time"])),
                "x1": last_t,
                "y0": z["bottom"],
                "y1": z["top"],
                "fill": color,
                "line": line,
                "label": f"OB {z['direction']}",
            }
        )

    markers = []
    for e in smc.events:
        if int(e["time"]) < t0:
            continue
        markers.append(
            {
                "t": e["time_label"],
                "price": e["broken_level"],
                "text": e["kind"],
                "direction": e["direction"],
            }
        )

    levels = []
    liq = smc.liquidity or {}
    if liq.get("nearest_bsl"):
        levels.append({"price": liq["nearest_bsl"], "label": "BSL", "kind": "liq"})
    if liq.get("nearest_ssl"):
        levels.append({"price": liq["nearest_ssl"], "label": "SSL", "kind": "liq"})
    dr = smc.dealing_range or {}
    if dr.get("equilibrium"):
        levels.append({"price": dr["equilibrium"], "label": "EQ 50%", "kind": "eq"})

    n = len(candles)
    ema21 = (ema_series.get("ema21") or [])[-n:]
    ema50 = (ema_series.get("ema50") or [])[-n:]
    # pad if needed
    if len(ema21) < n:
        ema21 = [None] * (n - len(ema21)) + ema21
    if len(ema50) < n:
        ema50 = [None] * (n - len(ema50)) + ema50

    return {
        "candles": candles,
        "ema21": ema21,
        "ema50": ema50,
        "shapes": shapes[-18:],
        "markers": markers[-16:],
        "levels": levels,
    }


def _analyze_frame(tf: str, df: pd.DataFrame) -> dict[str, Any]:
    smc = analyze_smc(df, swing_n=SWING_N.get(tf, 5), fvg_min_pct=FVG_MIN.get(tf, 0.0004))
    ta, ema_series = compute_ta(df)
    scored = score_tf(smc, ta)
    text = narrative_tf(tf, smc, ta, scored)
    from dataclasses import asdict

    smc_dict = asdict(smc)
    return {
        "tf": tf,
        "title": TF_META[tf]["title"],
        "weight": TF_META[tf]["weight"],
        "color": TF_META[tf].get("color"),
        "bars": int(len(df)),
        "score": scored,
        "smc": smc_dict,
        "ta": ta_dict(ta),
        "narrative": text,
        "chart": _chart_payload(df, smc, ema_series),
    }


def analyze_query(raw: str) -> dict[str, Any]:
    parsed = parse_query(raw)
    try:
        bundle = load_market_cached(parsed.symbol, parsed.preferred_exchange)
    except DataError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DataError(str(exc)) from exc

    tfs: dict[str, dict] = {}
    errors: list[str] = []
    for tf in TF_ORDER:
        df = bundle.frames.get(tf)
        if df is None or len(df) < 80:
            errors.append(f"{tf}: داده کافی نیست")
            continue
        try:
            tfs[tf] = _analyze_frame(tf, df)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{tf}: {exc}")

    if not tfs:
        raise DataError("تحلیل هیچ تایم‌فریمی موفق نشد. " + " | ".join(errors))

    conf = confluence(tfs)
    full_report = _full_report(parsed.symbol, bundle, conf, tfs)

    tk = bundle.ticker
    payload = {
        "ok": True,
        "symbol": bundle.symbol,
        "base": parsed.base,
        "quote": parsed.quote,
        "exchange": bundle.exchange,
        "exchange_label": EXCHANGE_LABEL.get(bundle.exchange, bundle.exchange),
        "query": parsed.raw,
        "source_kind": parsed.source_kind,
        "price": tk.price,
        "change_pct": tk.change_pct,
        "high_24h": tk.high_24h,
        "low_24h": tk.low_24h,
        "volume": tk.volume,
        "quote_volume": tk.quote_volume,
        "confluence": conf,
        "timeframes": tfs,
        "report": full_report,
        "errors": errors,
        "disclaimer": "خروجی آموزشی است و توصیه سرمایه‌گذاری یا سیگنال تضمینی نیست.",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    return _clean(payload)


def _full_report(symbol: str, bundle, conf: dict, tfs: dict) -> str:
    tk = bundle.ticker
    chg = f"{tk.change_pct:+.2f}%" if tk.change_pct is not None else "—"
    lines = [
        f"گزارش SmartFlow — {symbol}",
        f"قیمت: {tk.price}   تغییر ۲۴س: {chg}   منبع: {EXCHANGE_LABEL.get(bundle.exchange, bundle.exchange)}",
        f"هم‌گرایی: {conf['bias_fa']}  |  امتیاز وزنی {conf['score']}/۱۰۰",
        "",
        conf["headline"],
        conf["setup"]["idea"],
    ]
    setup = conf["setup"]
    if setup.get("entry_zone") and setup["entry_zone"].get("low"):
        z = setup["entry_zone"]
        lines.append(f"ناحیه تمرکز: {z.get('kind')}  {z.get('low')} – {z.get('high')}")
    if setup.get("invalidation"):
        lines.append(f"باطل‌شدن نسبی سوگیری بالاتر: {setup['invalidation']}")
    if setup.get("targets"):
        lines.append("اهداف نقدینگی: " + " ، ".join(str(x) for x in setup["targets"]))
    lines.append("")
    for tf in TF_ORDER:
        block = tfs.get(tf)
        if not block:
            continue
        lines.append(block["narrative"])
        lines.append("")
    lines.append(conf["setup"]["disclaimer"])
    return "\n".join(lines)
