"""Scoring, confluence, and Persian narrative for each timeframe."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .smc import SMCResult
from .ta import TASnapshot


TF_ORDER = ("4h", "1h", "30m", "15m", "5m", "1m")

TF_META = {
    "4h": {"title": "۴ ساعته", "weight": 0.32, "noise": False, "color": "#7aa2ff"},
    "1h": {"title": "۱ ساعته", "weight": 0.24, "noise": False, "color": "#b49cff"},
    "30m": {"title": "۳۰ دقیقه", "weight": 0.16, "noise": False, "color": "#2ee6c5"},
    "15m": {"title": "۱۵ دقیقه", "weight": 0.12, "noise": True, "color": "#5ee7ff"},
    "5m": {"title": "۵ دقیقه", "weight": 0.10, "noise": True, "color": "#ffc857"},
    "1m": {"title": "۱ دقیقه", "weight": 0.06, "noise": True, "color": "#ff8aa0"},
}

BIAS_FA = {
    "strongly_bullish": "قوی صعودی",
    "bullish": "صعودی",
    "neutral": "خنثی / رنج",
    "bearish": "نزولی",
    "strongly_bearish": "قوی نزولی",
}


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def score_tf(smc: SMCResult, ta: TASnapshot) -> dict[str, Any]:
    score = 50.0
    reasons: list[str] = []

    ev = smc.last_event
    if ev:
        decay = max(0.4, 1.0 - ev["bars_ago"] / 90.0)
        mag = 12.0 if ev["kind"] == "CHoCH" else 8.0
        delta = mag * decay * (1 if ev["direction"] == "bullish" else -1)
        score += delta
        reasons.append(
            f"{ev['kind']} {('صعودی' if ev['direction']=='bullish' else 'نزولی')} "
            f"({ev['bars_ago']} کندل پیش)"
        )

    if "صعودی" in smc.structure_label:
        score += 6
        reasons.append("ساختار HH/HL")
    elif "نزولی" in smc.structure_label:
        score -= 6
        reasons.append("ساختار LH/LL")

    pd = smc.premium_discount
    if smc.trend == "bullish" and pd == "discount":
        score += 8
        reasons.append("روند صعودی + قیمت در دیسکانت")
    elif smc.trend == "bearish" and pd == "premium":
        score -= 8
        reasons.append("روند نزولی + قیمت در پرمیوم")
    elif smc.trend == "bullish" and pd == "premium":
        score -= 3
        reasons.append("روند صعودی اما قیمت در پرمیوم (گران)")
    elif smc.trend == "bearish" and pd == "discount":
        score += 3
        reasons.append("روند نزولی اما قیمت در دیسکانت (ارزان)")

    near = smc.nearby or {}

    def _near_boost(key: str, sign: int, label: str) -> None:
        nonlocal score
        z = near.get(key)
        if not z or z.get("status") in ("filled", "invalidated"):
            return
        dist_atr = z.get("distance_atr")
        if dist_atr is None:
            return
        if dist_atr <= 1.6:
            boost = 7 if z.get("inside") else 5
            if z.get("status") == "fresh":
                boost += 1
            score += sign * boost
            reasons.append(label)

    _near_boost("bullish_ob", +1, "نزدیک اردر بلاک صعودی")
    _near_boost("bearish_ob", -1, "نزدیک اردر بلاک نزولی")
    _near_boost("bullish_fvg", +1, "نزدیک FVG صعودی")
    _near_boost("bearish_fvg", -1, "نزدیک FVG نزولی")

    if smc.sweeps:
        sw = smc.sweeps[-1]
        if sw["direction"] == "ssl":
            score += 7
            reasons.append("سوئیپ نقدینگی فروش (SSL)")
        else:
            score -= 7
            reasons.append("سوئیپ نقدینگی خرید (BSL)")

    if smc.displacement.get("present"):
        if smc.displacement["direction"] == "bullish":
            score += 4
            reasons.append("جابه‌جایی صعودی")
        else:
            score -= 4
            reasons.append("جابه‌جایی نزولی")

    if ta.ema_stack == "bullish":
        score += 8
        reasons.append("چینش EMA صعودی")
    elif ta.ema_stack == "bearish":
        score -= 8
        reasons.append("چینش EMA نزولی")

    if ta.rsi_state == "oversold":
        score += 5
        reasons.append("RSI اشباع فروش")
    elif ta.rsi_state == "overbought":
        score -= 5
        reasons.append("RSI اشباع خرید")
    elif ta.rsi_state == "bullish":
        score += 2
    elif ta.rsi_state == "bearish":
        score -= 2

    if ta.macd_cross in ("bullish", "bullish_cross"):
        score += 4 if "cross" in ta.macd_cross else 3
        if "cross" in ta.macd_cross:
            reasons.append("کراس صعودی MACD")
    elif ta.macd_cross in ("bearish", "bearish_cross"):
        score -= 4 if "cross" in ta.macd_cross else 3
        if "cross" in ta.macd_cross:
            reasons.append("کراس نزولی MACD")

    if ta.divergence in ("bullish", "hidden_bullish"):
        score += 6 if ta.divergence == "bullish" else 3
        reasons.append("واگرایی مثبت RSI")
    elif ta.divergence in ("bearish", "hidden_bearish"):
        score -= 6 if ta.divergence == "bearish" else 3
        reasons.append("واگرایی منفی RSI")

    if ta.vs_vwap == "above":
        score += 2
    elif ta.vs_vwap == "below":
        score -= 2

    if ta.trend_strength == "weak_range":
        score = 50 + (score - 50) * 0.45
        reasons.append("ADX ضعیف — بازار رنج، امتیاز به سمت خنثی میل کرد")

    score = _clamp(score)

    if score >= 72:
        bias = "strongly_bullish"
    elif score >= 58:
        bias = "bullish"
    elif score <= 28:
        bias = "strongly_bearish"
    elif score <= 42:
        bias = "bearish"
    else:
        bias = "neutral"

    confidence = 55
    if ta.trend_strength in ("strong", "very_strong"):
        confidence += 15
    if ev and ev["bars_ago"] <= 20:
        confidence += 10
    if ta.trend_strength == "weak_range":
        confidence -= 15
    confidence = int(_clamp(confidence, 30, 90))

    return {
        "score": round(score, 1),
        "bias": bias,
        "bias_fa": BIAS_FA[bias],
        "confidence": confidence,
        "reasons": reasons[:8],
    }


def _fmt(x: float | None, digits: int | None = None) -> str:
    if x is None:
        return "—"
    ax = abs(float(x))
    if digits is not None:
        return f"{x:,.{digits}f}"
    if ax >= 1000:
        return f"{x:,.2f}"
    if ax >= 1:
        return f"{x:,.4f}".rstrip("0").rstrip(".")
    if ax >= 0.01:
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return f"{x:.8f}".rstrip("0").rstrip(".")


def narrative_tf(tf: str, smc: SMCResult, ta: TASnapshot, scored: dict) -> str:
    title = TF_META[tf]["title"]
    lines = [f"▸ تایم‌فریم {title} — سوگیری: {scored['bias_fa']} (امتیاز {scored['score']}/۱۰۰)"]

    if smc.last_event:
        ev = smc.last_event
        fa = "صعودی" if ev["direction"] == "bullish" else "نزولی"
        lines.append(
            f"ساختار بازار: {smc.structure_label}. آخرین شکست: {ev['kind']} {fa} "
            f"در {_fmt(ev['broken_level'])} حدود {ev['bars_ago']} کندل پیش."
        )
    else:
        lines.append(f"ساختار بازار: {smc.structure_label}. شکست تأییدشدهٔ تازه‌ای دیده نشد.")

    pd_map = {"premium": "پرمیوم (گران)", "discount": "دیسکانت (ارزان)", "equilibrium": "تعادل (۵۰٪)"}
    if smc.dealing_range:
        dr = smc.dealing_range
        pos_pct = dr["position"] * 100
        extra = ""
        if dr["position"] < 0:
            extra = " — قیمت زیر محدوده شکسته (گسترش نزولی)"
        elif dr["position"] > 1:
            extra = " — قیمت بالای محدوده شکسته (گسترش صعودی)"
        lines.append(
            f"محدودهٔ معاملاتی: {_fmt(dr['low'])} تا {_fmt(dr['high'])} — "
            f"قیمت در {pd_map.get(smc.premium_discount, smc.premium_discount)} "
            f"(موقعیت {pos_pct:.0f}٪ محدوده){extra}."
        )
        ote = smc.ote or {}
        if ote:
            inside = "داخل OTE است" if ote.get("in_ote") else "خارج از OTE است"
            lines.append(
                f"ناحیه ورود بهینه (OTE / ۰٫۶۲–۰٫۷۹): {_fmt(ote.get('low'))} تا {_fmt(ote.get('high'))} — قیمت {inside}."
            )

    live_obs = [z for z in smc.order_blocks if z["status"] != "invalidated"]
    if live_obs:
        parts = []
        for z in live_obs[-3:]:
            parts.append(
                f"{'صعودی' if z['direction']=='bullish' else 'نزولی'} "
                f"{_fmt(z['bottom'])}–{_fmt(z['top'])} ({z['status']})"
            )
        lines.append("اردر بلاک‌های فعال: " + "؛ ".join(parts) + ".")
    else:
        lines.append("اردر بلاک فعالِ تأییدشده‌ای در پنجرهٔ فعلی نیست.")

    live_fvg = [z for z in smc.fvgs if z["status"] != "filled"]
    if live_fvg:
        parts = []
        for z in live_fvg[-3:]:
            parts.append(
                f"{'صعودی' if z['direction']=='bullish' else 'نزولی'} "
                f"{_fmt(z['bottom'])}–{_fmt(z['top'])} ({z['status']})"
            )
        lines.append("FVGهای باز: " + "؛ ".join(parts) + ".")
    else:
        lines.append("گپ ارزش منصفانهٔ پرنشده‌ای باقی نمانده.")

    liq = smc.liquidity or {}
    bits = []
    if liq.get("nearest_bsl"):
        bits.append(f"نقدینگی خرید (BSL) نزدیک {_fmt(liq['nearest_bsl'])}")
    if liq.get("nearest_ssl"):
        bits.append(f"نقدینگی فروش (SSL) نزدیک {_fmt(liq['nearest_ssl'])}")
    if smc.equal_highs:
        bits.append(f"سقف‌های برابر حوالی {_fmt(smc.equal_highs[-1]['price'])}")
    if smc.equal_lows:
        bits.append(f"کف‌های برابر حوالی {_fmt(smc.equal_lows[-1]['price'])}")
    if bits:
        lines.append("نقدینگی: " + " — ".join(bits) + ".")

    if smc.sweeps:
        sw = smc.sweeps[-1]
        if sw["direction"] == "ssl":
            lines.append(
                f"سوئیپ اخیر: کندل {_fmt(sw['close'])} سایه را زیر {_fmt(sw['level'])} برد و برگشت (اخذ نقدینگی فروش)."
            )
        else:
            lines.append(
                f"سوئیپ اخیر: کندل {_fmt(sw['close'])} سایه را بالای {_fmt(sw['level'])} برد و برگشت (اخذ نقدینگی خرید)."
            )

    rsi = f"{ta.rsi:.1f}" if ta.rsi is not None else "—"
    adx = f"{ta.adx:.1f}" if ta.adx is not None else "—"
    lines.append(
        f"تکنیکال: RSI {rsi} ({ta.rsi_state})، MACD {ta.macd_cross}، "
        f"EMA {ta.ema_stack}، ADX {adx} ({ta.trend_strength})، حجم {ta.volume_state}."
    )
    if ta.notes:
        lines.append("نکات: " + " ".join(ta.notes[:3]))

    if TF_META[tf]["noise"]:
        lines.append("هشدار: این تایم‌فریم نویز بالایی دارد و نباید به‌تنهایی مبنای تصمیم باشد.")

    inv = None
    if smc.liquidity:
        if scored["bias"] in ("bullish", "strongly_bullish") and smc.liquidity.get("nearest_ssl"):
            inv = smc.liquidity["nearest_ssl"]
        elif scored["bias"] in ("bearish", "strongly_bearish") and smc.liquidity.get("nearest_bsl"):
            inv = smc.liquidity["nearest_bsl"]
    if inv:
        lines.append(f"باطل‌شدن نسبی سوگیری این تایم: عبور پایدار از {_fmt(inv)}.")

    return "\n".join(lines)


def confluence(tf_payloads: dict[str, dict]) -> dict[str, Any]:
    weighted = 0.0
    wsum = 0.0
    votes = {"bull": 0.0, "bear": 0.0, "flat": 0.0}
    cards = []
    for tf, meta in TF_META.items():
        block = tf_payloads.get(tf)
        if not block:
            continue
        s = float(block["score"]["score"])
        w = meta["weight"]
        weighted += s * w
        wsum += w
        bias = block["score"]["bias"]
        if "bull" in bias:
            votes["bull"] += w
        elif "bear" in bias:
            votes["bear"] += w
        else:
            votes["flat"] += w
        cards.append(
            {
                "tf": tf,
                "title": meta["title"],
                "bias": bias,
                "bias_fa": block["score"]["bias_fa"],
                "score": s,
                "color": meta.get("color"),
            }
        )

    total = weighted / wsum if wsum else 50.0
    if total >= 68:
        bias = "strongly_bullish"
    elif total >= 56:
        bias = "bullish"
    elif total <= 32:
        bias = "strongly_bearish"
    elif total <= 44:
        bias = "bearish"
    else:
        bias = "neutral"

    htf = tf_payloads.get("4h", {}).get("score", {})
    ltf_conflict = False
    if htf:
        h = htf.get("bias", "neutral")
        m1 = tf_payloads.get("1m", {}).get("score", {}).get("bias", "neutral")
        if ("bull" in h and "bear" in m1) or ("bear" in h and "bull" in m1):
            ltf_conflict = True

    headline = _headline(bias, votes, ltf_conflict, tf_payloads)
    setup = _setup(bias, tf_payloads)
    return {
        "score": round(total, 1),
        "bias": bias,
        "bias_fa": BIAS_FA[bias],
        "votes": votes,
        "cards": cards,
        "headline": headline,
        "setup": setup,
        "htf_ltf_conflict": ltf_conflict,
    }


def _headline(bias: str, votes: dict, conflict: bool, tfs: dict) -> str:
    fa = BIAS_FA[bias]
    h4 = tfs.get("4h", {}).get("score", {})
    h1 = tfs.get("1h", {}).get("score", {})
    m30 = tfs.get("30m", {}).get("score", {})
    parts = [f"هم‌گرایی تایم‌فریم‌ها: {fa}."]
    if h4:
        parts.append(f"۴ ساعته {h4.get('bias_fa', '—')} است")
    if h1:
        parts.append(f"۱ ساعته {h1.get('bias_fa', '—')}")
    if m30:
        parts.append(f"۳۰ دقیقه {m30.get('bias_fa', '—')}")
    msg = " ".join(parts) + "."
    if conflict:
        msg += " تایم‌های خیلی پایین با روند بالاتر در تضادند — اولویت با ۴ ساعته و ۱ ساعته است."
    if votes["flat"] >= 0.4:
        msg += " بخش قابل‌توجهی از تایم‌فریم‌ها رنج هستند؛ از ورود در میانهٔ محدوده پرهیز کنید."
    return msg


def _setup(bias: str, tfs: dict) -> dict[str, Any]:
    h4 = tfs.get("4h", {})
    h1 = tfs.get("1h", {})
    smc4 = h4.get("smc") or {}
    smc1 = h1.get("smc") or {}
    last = (h1.get("ta") or h4.get("ta") or {}).get("last_close")

    direction = "wait"
    idea = "منتظر رسیدن قیمت به ناحیهٔ ارزش (اردر بلاک / FVG / OTE) هم‌جهت با ۴ ساعته بمانید."
    entry = None
    invalid = None
    targets: list[float] = []

    if bias in ("bullish", "strongly_bullish"):
        direction = "long_bias"
        idea = (
            "سوگیری کلی خرید است. به‌جای تعقیب قیمت، منتظر برگشت به دیسکانت، "
            "FVG یا اردر بلاک صعودی ۱ ساعته/۴ ساعته بمانید و تأیید ساختار پایین‌تر را بگیرید."
        )
        for src in (smc1, smc4):
            z = (src.get("nearby") or {}).get("bullish_ob") or (src.get("nearby") or {}).get("bullish_fvg")
            if z and not entry:
                entry = {"low": z["bottom"], "high": z["top"], "kind": z["kind"]}
        invalid = (smc4.get("liquidity") or {}).get("nearest_ssl") or (smc1.get("liquidity") or {}).get("nearest_ssl")
        t1 = (smc1.get("liquidity") or {}).get("nearest_bsl")
        t2 = (smc4.get("liquidity") or {}).get("nearest_bsl")
        targets = [x for x in (t1, t2) if x and (last is None or x > last)]
    elif bias in ("bearish", "strongly_bearish"):
        direction = "short_bias"
        idea = (
            "سوگیری کلی فروش است. ورود منطقی نزدیک پرمیوم، FVG یا اردر بلاک نزولی "
            "تایم بالاتر است؛ نه در کف‌های هیجانی."
        )
        for src in (smc1, smc4):
            z = (src.get("nearby") or {}).get("bearish_ob") or (src.get("nearby") or {}).get("bearish_fvg")
            if z and not entry:
                entry = {"low": z["bottom"], "high": z["top"], "kind": z["kind"]}
        invalid = (smc4.get("liquidity") or {}).get("nearest_bsl") or (smc1.get("liquidity") or {}).get("nearest_bsl")
        t1 = (smc1.get("liquidity") or {}).get("nearest_ssl")
        t2 = (smc4.get("liquidity") or {}).get("nearest_ssl")
        targets = [x for x in (t1, t2) if x and (last is None or x < last)]
    else:
        idea = (
            "هم‌گرایی خنثی است. یا صبر کنید تا ۴ ساعته CHoCH بدهد، "
            "یا فقط در دو سر محدوده (EQH/EQL) و با حجم کم معامله کنید."
        )
        dr = smc4.get("dealing_range") or smc1.get("dealing_range") or {}
        if dr:
            entry = {"low": dr.get("low"), "high": dr.get("high"), "kind": "range"}

    return {
        "direction": direction,
        "idea": idea,
        "entry_zone": entry,
        "invalidation": invalid,
        "targets": targets[:3],
        "last_price": last,
        "disclaimer": "این خروجی آموزشی است و توصیهٔ مالی یا سیگنال تضمینی نیست.",
    }


def ta_dict(ta: TASnapshot) -> dict[str, Any]:
    return asdict(ta)
