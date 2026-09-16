"""Fetch OHLCV from public exchange APIs with automatic fallback."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import requests


INTERVALS = {
    "1m": {"binance": "1m", "okx": "1m", "bitget": "1min", "mexc": "1m", "kucoin": "1min", "gate": "1m"},
    "5m": {"binance": "5m", "okx": "5m", "bitget": "5min", "mexc": "5m", "kucoin": "5min", "gate": "5m"},
    "15m": {"binance": "15m", "okx": "15m", "bitget": "15min", "mexc": "15m", "kucoin": "15min", "gate": "15m"},
    "30m": {"binance": "30m", "okx": "30m", "bitget": "30min", "mexc": "30m", "kucoin": "30min", "gate": "30m"},
    "1h": {"binance": "1h", "okx": "1H", "bitget": "1h", "mexc": "60m", "kucoin": "1hour", "gate": "1h"},
    "4h": {"binance": "4h", "okx": "4H", "bitget": "4h", "mexc": "4h", "kucoin": "4hour", "gate": "4h"},
}

TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h")
TIMEFRAME_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
}

HEADERS = {
    "User-Agent": "SmartFlowAnalyzer/1.0 (educational; market-data)",
    "Accept": "application/json",
}


class DataError(RuntimeError):
    pass


@dataclass
class Ticker:
    price: float
    change_pct: float | None
    high_24h: float | None
    low_24h: float | None
    volume: float | None
    quote_volume: float | None


@dataclass
class MarketBundle:
    symbol: str
    exchange: str
    ticker: Ticker
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        raise DataError("کندلی دریافت نشد.")
    df = pd.DataFrame(rows)
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    if len(df) < 80:
        raise DataError(f"تعداد کندل کافی نیست ({len(df)}). حداقل ۸۰ کندل لازم است.")
    return df


def _binance_style_klines(url: str, params: dict, session: requests.Session) -> list[dict]:
    r = session.get(url, params=params, timeout=12)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("code") not in (None, 0, "0"):
        raise DataError(str(data.get("msg") or data))
    if not isinstance(data, list):
        raise DataError(str(data))
    rows = []
    for k in data:
        rows.append(
            {
                "time": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            }
        )
    return rows


def _okx_symbol(symbol: str) -> str:
    # BTCUSDT -> BTC-USDT
    for q in ("USDT", "USDC", "USD", "BTC", "ETH"):
        if symbol.endswith(q) and len(symbol) > len(q):
            return f"{symbol[:-len(q)]}-{q}"
    return symbol


def fetch_klines(symbol: str, tf: str, exchange: str, session: requests.Session, limit: int = 1000) -> list[dict]:
    maps = INTERVALS[tf]
    if exchange in ("binance", "binance_us", "mexc"):
        host = {
            "binance": "https://api.binance.com/api/v3/klines",
            "binance_us": "https://api.binance.us/api/v3/klines",
            "mexc": "https://api.mexc.com/api/v3/klines",
        }[exchange]
        interval = maps["mexc"] if exchange == "mexc" else maps["binance"]
        cap = 500 if exchange == "mexc" else 1000
        return _binance_style_klines(host, {"symbol": symbol, "interval": interval, "limit": min(limit, cap)}, session)

    if exchange == "bitget":
        r = session.get(
            "https://api.bitget.com/api/v2/spot/market/candles",
            params={"symbol": symbol, "granularity": maps["bitget"], "limit": min(limit, 200)},
            timeout=12,
        )
        r.raise_for_status()
        payload = r.json()
        if str(payload.get("code")) not in ("00000", "0"):
            raise DataError(payload.get("msg") or "bitget error")
        rows = []
        for k in payload.get("data") or []:
            rows.append(
                {
                    "time": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
            )
        return rows

    if exchange == "okx":
        inst = _okx_symbol(symbol)
        rows: list[dict] = []
        after = None
        bar = maps["okx"]
        remaining = min(limit, 750)
        while remaining > 0:
            params: dict[str, Any] = {"instId": inst, "bar": bar, "limit": min(300, remaining)}
            if after:
                params["after"] = after
            r = session.get("https://www.okx.com/api/v5/market/history-candles", params=params, timeout=12)
            if r.status_code >= 400:
                r = session.get("https://www.okx.com/api/v5/market/candles", params=params, timeout=12)
            r.raise_for_status()
            payload = r.json()
            if str(payload.get("code")) != "0":
                raise DataError(payload.get("msg") or "okx error")
            chunk = payload.get("data") or []
            if not chunk:
                break
            for k in chunk:
                rows.append(
                    {
                        "time": int(k[0]),
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                    }
                )
            after = chunk[-1][0]
            remaining -= len(chunk)
            if len(chunk) < 50:
                break
        return rows

    if exchange == "kucoin":
        r = session.get(
            "https://api.kucoin.com/api/v1/market/candles",
            params={"symbol": _okx_symbol(symbol), "type": maps["kucoin"]},
            timeout=12,
        )
        r.raise_for_status()
        payload = r.json()
        if str(payload.get("code")) != "200000":
            raise DataError(payload.get("msg") or "kucoin error")
        rows = []
        for k in payload.get("data") or []:
            # [time, open, close, high, low, volume, turnover]
            rows.append(
                {
                    "time": int(k[0]) * 1000 if int(k[0]) < 10_000_000_000 else int(k[0]),
                    "open": float(k[1]),
                    "close": float(k[2]),
                    "high": float(k[3]),
                    "low": float(k[4]),
                    "volume": float(k[5]),
                }
            )
        return rows[:limit]

    if exchange == "gate":
        pair = _okx_symbol(symbol).replace("-", "_")
        r = session.get(
            "https://api.gateio.ws/api/v4/spot/candlesticks",
            params={"currency_pair": pair, "interval": maps["gate"], "limit": min(limit, 1000)},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("label"):
            raise DataError(str(data))
        rows = []
        for k in data:
            # [timestamp, quote_volume, close, high, low, open, base_volume]
            ts = int(k[0])
            if ts < 10_000_000_000:
                ts *= 1000
            rows.append(
                {
                    "time": ts,
                    "open": float(k[5]),
                    "high": float(k[3]),
                    "low": float(k[4]),
                    "close": float(k[2]),
                    "volume": float(k[6]),
                }
            )
        return rows

    raise DataError(f"صرافی ناشناخته: {exchange}")


def fetch_ticker(symbol: str, exchange: str, session: requests.Session) -> Ticker:
    try:
        if exchange in ("binance", "binance_us"):
            host = "https://api.binance.com" if exchange == "binance" else "https://api.binance.us"
            r = session.get(f"{host}/api/v3/ticker/24hr", params={"symbol": symbol}, timeout=10)
            r.raise_for_status()
            d = r.json()
            return Ticker(
                price=float(d["lastPrice"]),
                change_pct=float(d["priceChangePercent"]),
                high_24h=float(d["highPrice"]),
                low_24h=float(d["lowPrice"]),
                volume=float(d["volume"]),
                quote_volume=float(d["quoteVolume"]),
            )
        if exchange == "mexc":
            r = session.get("https://api.mexc.com/api/v3/ticker/24hr", params={"symbol": symbol}, timeout=10)
            r.raise_for_status()
            d = r.json()
            return Ticker(
                price=float(d["lastPrice"]),
                change_pct=float(d.get("priceChangePercent") or 0),
                high_24h=float(d["highPrice"]),
                low_24h=float(d["lowPrice"]),
                volume=float(d.get("volume") or 0),
                quote_volume=float(d.get("quoteVolume") or 0),
            )
        if exchange == "bitget":
            r = session.get(
                "https://api.bitget.com/api/v2/spot/market/tickers",
                params={"symbol": symbol},
                timeout=10,
            )
            r.raise_for_status()
            d = (r.json().get("data") or [None])[0]
            if not d:
                raise DataError("no ticker")
            last = float(d["lastPr"])
            open_ = float(d["open"])
            chg = ((last - open_) / open_ * 100) if open_ else None
            return Ticker(last, chg, float(d["high24h"]), float(d["low24h"]), float(d.get("baseVolume") or 0), float(d.get("quoteVolume") or 0))
        if exchange == "okx":
            r = session.get("https://www.okx.com/api/v5/market/ticker", params={"instId": _okx_symbol(symbol)}, timeout=10)
            r.raise_for_status()
            d = (r.json().get("data") or [None])[0]
            if not d:
                raise DataError("no ticker")
            last = float(d["last"])
            open_ = float(d["open24h"])
            chg = ((last - open_) / open_ * 100) if open_ else None
            return Ticker(last, chg, float(d["high24h"]), float(d["low24h"]), float(d.get("vol24h") or 0), float(d.get("volCcy24h") or 0))
        if exchange == "kucoin":
            r = session.get(
                "https://api.kucoin.com/api/v1/market/stats",
                params={"symbol": _okx_symbol(symbol)},
                timeout=10,
            )
            r.raise_for_status()
            d = r.json().get("data") or {}
            last = float(d["last"])
            chg = float(d.get("changeRate") or 0) * 100
            return Ticker(last, chg, float(d.get("high") or last), float(d.get("low") or last), float(d.get("vol") or 0), float(d.get("volValue") or 0))
        if exchange == "gate":
            pair = _okx_symbol(symbol).replace("-", "_")
            r = session.get("https://api.gateio.ws/api/v4/spot/tickers", params={"currency_pair": pair}, timeout=10)
            r.raise_for_status()
            d = r.json()[0]
            last = float(d["last"])
            chg = float(d.get("change_percentage") or 0)
            return Ticker(last, chg, float(d.get("high_24h") or last), float(d.get("low_24h") or last), float(d.get("base_volume") or 0), float(d.get("quote_volume") or 0))
    except Exception as exc:  # noqa: BLE001
        raise DataError(str(exc)) from exc
    raise DataError("ticker unsupported")


def _ticker_from_frame(df: pd.DataFrame) -> Ticker:
    last = float(df["close"].iloc[-1])
    # approximate 24h from 1h or 5m if possible
    span = 24 * 3600 * 1000
    window = df[df["time"] >= int(df["time"].iloc[-1]) - span]
    if len(window) >= 2:
        open_ = float(window["open"].iloc[0])
        chg = (last - open_) / open_ * 100 if open_ else None
        return Ticker(last, chg, float(window["high"].max()), float(window["low"].min()), float(window["volume"].sum()), None)
    return Ticker(last, None, float(df["high"].tail(24).max()), float(df["low"].tail(24).min()), None, None)


EXCHANGE_ORDER = ["binance", "binance_us", "mexc", "okx", "bitget", "kucoin", "gate"]
EXCHANGE_LABEL = {
    "binance": "Binance",
    "binance_us": "Binance.US",
    "mexc": "MEXC",
    "okx": "OKX",
    "bitget": "Bitget",
    "kucoin": "KuCoin",
    "gate": "Gate.io",
}


def load_market(symbol: str, preferred: str | None = None) -> MarketBundle:
    session = _session()
    order = list(EXCHANGE_ORDER)
    if preferred in order:
        order.remove(preferred)
        order.insert(0, preferred)
    # Binance.com is often geo-blocked; keep it first only if preferred
    if preferred != "binance" and "binance" in order:
        order.remove("binance")
        order.append("binance")

    errors: list[str] = []
    tfs = list(TIMEFRAMES)

    for ex in order:
        try:
            frames: dict[str, pd.DataFrame] = {}

            def _one(tf_name: str):
                rows = fetch_klines(symbol, tf_name, ex, _session())
                return tf_name, _to_df(rows)

            with ThreadPoolExecutor(max_workers=6) as pool:
                futs = [pool.submit(_one, tf) for tf in tfs]
                for fut in as_completed(futs):
                    tf_name, frame = fut.result()
                    frames[tf_name] = frame
            try:
                ticker = fetch_ticker(symbol, ex, session)
            except Exception:
                ticker = _ticker_from_frame(frames.get("1h") or frames["5m"])
            return MarketBundle(symbol=symbol, exchange=ex, ticker=ticker, frames=frames, notes=errors)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{EXCHANGE_LABEL.get(ex, ex)}: {exc}")
            continue

    # last chance: maybe quote is USDT but pair lives as USDC
    if symbol.endswith("USDT"):
        alt = symbol[:-4] + "USDC"
        try:
            return load_market(alt, preferred)
        except Exception:
            pass

    raise DataError(
        "نتوانستم دادهٔ کندل این نماد را از صرافی‌های عمومی بگیرم.\n" + " | ".join(errors[-4:])
    )


# tiny in-memory cache so the UI can re-render without hammering APIs
_CACHE: dict[str, tuple[float, MarketBundle]] = {}
CACHE_TTL = 20.0


def load_market_cached(symbol: str, preferred: str | None = None) -> MarketBundle:
    key = f"{symbol}|{preferred or ''}"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    bundle = load_market(symbol, preferred)
    _CACHE[key] = (now, bundle)
    return bundle
