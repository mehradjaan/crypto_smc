"""Parse TradingView / exchange URLs and free-text coin names into a spot symbol."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse


COIN_ALIASES: dict[str, str] = {
    "btc": "BTCUSDT",
    "bitcoin": "BTCUSDT",
    "xbt": "BTCUSDT",
    "بیتکوین": "BTCUSDT",
    "بیت کوین": "BTCUSDT",
    "بیت‌کوین": "BTCUSDT",
    "eth": "ETHUSDT",
    "ethereum": "ETHUSDT",
    "اتر": "ETHUSDT",
    "اتریوم": "ETHUSDT",
    "sol": "SOLUSDT",
    "solana": "SOLUSDT",
    "سولانا": "SOLUSDT",
    "bnb": "BNBUSDT",
    "binance": "BNBUSDT",
    "بایننس": "BNBUSDT",
    "xrp": "XRPUSDT",
    "ripple": "XRPUSDT",
    "ریپل": "XRPUSDT",
    "doge": "DOGEUSDT",
    "dogecoin": "DOGEUSDT",
    "دوج": "DOGEUSDT",
    "دوجکوین": "DOGEUSDT",
    "ada": "ADAUSDT",
    "cardano": "ADAUSDT",
    "کاردانو": "ADAUSDT",
    "avax": "AVAXUSDT",
    "avalanche": "AVAXUSDT",
    "آوالانچ": "AVAXUSDT",
    "link": "LINKUSDT",
    "chainlink": "LINKUSDT",
    "لینک": "LINKUSDT",
    "ton": "TONUSDT",
    "toncoin": "TONUSDT",
    "تون": "TONUSDT",
    "sui": "SUIUSDT",
    "near": "NEARUSDT",
    "apt": "APTUSDT",
    "dot": "DOTUSDT",
    "polkadot": "DOTUSDT",
    "پولکادات": "DOTUSDT",
    "matic": "MATICUSDT",
    "pol": "POLUSDT",
    "polygon": "POLUSDT",
    "arb": "ARBUSDT",
    "op": "OPUSDT",
    "inj": "INJUSDT",
    "fet": "FETUSDT",
    "pepe": "PEPEUSDT",
    "پپه": "PEPEUSDT",
    "wif": "WIFUSDT",
    "trx": "TRXUSDT",
    "tron": "TRXUSDT",
    "ترون": "TRXUSDT",
    "ltc": "LTCUSDT",
    "litecoin": "LTCUSDT",
    "لایتکوین": "LTCUSDT",
    "uni": "UNIUSDT",
    "atom": "ATOMUSDT",
    "fil": "FILUSDT",
    "aave": "AAVEUSDT",
    "mkr": "MKRUSDT",
    "tao": "TAOUSDT",
    "render": "RENDERUSDT",
    "rndr": "RENDERUSDT",
    "shib": "SHIBUSDT",
    "شیبا": "SHIBUSDT",
    "bch": "BCHUSDT",
    "etc": "ETCUSDT",
    "xlm": "XLMUSDT",
    "algo": "ALGOUSDT",
    "icp": "ICPUSDT",
    "hbar": "HBARUSDT",
    "vet": "VETUSDT",
    "sand": "SANDUSDT",
    "mana": "MANAUSDT",
    "axs": "AXSUSDT",
    "gala": "GALAUSDT",
    "ape": "APEUSDT",
    "ldo": "LDOUSDT",
    "crv": "CRVUSDT",
    "mpepe": "1000PEPEUSDT",
    "1000pepe": "1000PEPEUSDT",
    "bonk": "BONKUSDT",
    "floki": "FLOKIUSDT",
    "sei": "SEIUSDT",
    "tia": "TIAUSDT",
    "jup": "JUPUSDT",
    "wld": "WLDUSDT",
    "pyth": "PYTHUSDT",
    "ondo": "ONDOUSDT",
    "ena": "ENAUSDT",
    "bome": "BOMEUSDT",
    "not": "NOTUSDT",
    "kas": "KASUSDT",
    "runes": "RUNEUSDT",
    "rune": "RUNEUSDT",
}

QUOTE_ASSETS = (
    "USDT",
    "USDC",
    "BUSD",
    "FDUSD",
    "TUSD",
    "USD",
    "BTC",
    "ETH",
    "BNB",
    "EUR",
)

TV_EXCHANGE_HINTS = {
    "BINANCE": "binance",
    "BINANCEUS": "binance_us",
    "BYBIT": "bybit",
    "OKX": "okx",
    "OKEX": "okx",
    "BITGET": "bitget",
    "MEXC": "mexc",
    "KUCOIN": "kucoin",
    "GATE": "gate",
    "GATEIO": "gate",
    "KRAKEN": "kraken",
    "COINBASE": "coinbase",
    "COINBASEINTL": "coinbase",
}


@dataclass
class ParsedQuery:
    raw: str
    symbol: str
    base: str
    quote: str
    preferred_exchange: str | None
    source_kind: str  # url | symbol | name


def _clean(text: str) -> str:
    return (text or "").strip()


def _normalize_pair_token(token: str) -> str:
    token = unquote(token or "")
    token = token.strip()
    token = token.replace("\u200c", "")
    token = token.split("?")[0].split("#")[0]
    token = token.replace(" ", "")
    # perpetual / futures suffixes
    for suffix in (".P", ".PERP", "PERP", "_PERP", "-PERP", ".USD", ":PERP"):
        if token.upper().endswith(suffix) and suffix != ".USD":
            token = token[: -len(suffix)]
    token = token.replace("-", "").replace("_", "").replace("/", "").replace(":", "")
    token = re.sub(r"[^A-Za-z0-9]", "", token)
    return token.upper()


def _split_base_quote(symbol: str) -> tuple[str, str]:
    symbol = symbol.upper()
    for quote in QUOTE_ASSETS:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[: -len(quote)], quote
    return symbol, "USDT"


def _from_tv_symbol(tv: str) -> tuple[str | None, str]:
    """BINANCE:BTCUSDT or BITGET:ETHUSDT.P -> (exchange, BTCUSDT)."""
    tv = unquote(tv).strip()
    exchange = None
    pair = tv
    if ":" in tv:
        exchange, pair = tv.split(":", 1)
        exchange = TV_EXCHANGE_HINTS.get(exchange.upper().replace(" ", ""), exchange.lower())
    pair = pair.split("|")[0]
    pair = _normalize_pair_token(pair)
    if pair and not any(pair.endswith(q) for q in QUOTE_ASSETS):
        pair = pair + "USDT"
    return exchange, pair


def parse_query(raw: str) -> ParsedQuery:
    raw = _clean(raw)
    if not raw:
        raise ValueError("ورودی خالی است. نماد ارز یا آدرس چارت را وارد کنید.")

    preferred = None
    source_kind = "symbol"
    token = raw

    if re.match(r"^https?://", raw, re.I) or "tradingview.com" in raw.lower() or "binance." in raw.lower():
        source_kind = "url"
        url = raw if re.match(r"^https?://", raw, re.I) else "https://" + raw
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        qs = parse_qs(parsed.query)
        path = unquote(parsed.path or "")

        # TradingView: ?symbol=BINANCE:BTCUSDT
        if "symbol" in qs:
            preferred, token = _from_tv_symbol(qs["symbol"][0])
        elif "tradingview.com" in host:
            m = re.search(r"/symbols/([^/]+)/?", path, re.I)
            if m:
                preferred, token = _from_tv_symbol(m.group(1))
            else:
                # /chart/XXXX is a chart id, not a symbol — cannot recover
                raise ValueError(
                    "لینک تریدینگ‌ویو نماد ارز ندارد. از لینک کامل با پارامتر symbol استفاده کنید "
                    "(مثال: tradingview.com/chart/?symbol=BINANCE:BTCUSDT) یا خود نماد را بنویسید."
                )
        elif "binance" in host:
            preferred = "binance_us" if ".us" in host else "binance"
            m = re.search(r"/(?:trade|futures|spot)/([A-Za-z0-9_\-]+)", path, re.I)
            token = m.group(1) if m else ""
            if not token:
                m = re.search(r"symbol=([A-Za-z0-9_\-]+)", raw, re.I)
                token = m.group(1) if m else ""
            token = _normalize_pair_token(token)
        elif "bybit" in host:
            preferred = "bybit"
            m = re.search(r"/trade/(?:spot|usdt/)?([A-Za-z0-9_\-]+)", path, re.I)
            token = _normalize_pair_token(m.group(1) if m else path.split("/")[-1])
        elif "okx.com" in host:
            preferred = "okx"
            m = re.search(r"/trade-(?:spot|swap)/([A-Za-z0-9_\-]+)", path, re.I)
            token = _normalize_pair_token(m.group(1) if m else "")
        elif "bitget" in host:
            preferred = "bitget"
            m = re.search(r"/spot/([A-Za-z0-9_\-]+)", path, re.I)
            token = _normalize_pair_token(m.group(1) if m else "")
        elif "mexc" in host:
            preferred = "mexc"
            m = re.search(r"/exchange/([A-Za-z0-9_\-]+)", path, re.I)
            token = _normalize_pair_token(m.group(1) if m else "")
        elif "kucoin" in host:
            preferred = "kucoin"
            token = _normalize_pair_token(path.split("/")[-1])
        elif "gate.io" in host or "gateio" in host:
            preferred = "gate"
            m = re.search(r"/trade/([A-Za-z0-9_\-]+)", path, re.I)
            token = _normalize_pair_token(m.group(1) if m else "")
        elif "coinmarketcap.com" in host:
            source_kind = "name"
            m = re.search(r"/currencies/([^/]+)/?", path, re.I)
            name = (m.group(1) if m else "").lower().replace("-", "")
            token = COIN_ALIASES.get(name, name.upper() + "USDT")
        elif "coingecko.com" in host:
            source_kind = "name"
            m = re.search(r"/coins/([^/]+)/?", path, re.I)
            name = (m.group(1) if m else "").lower().replace("-", "")
            token = COIN_ALIASES.get(name, name.upper() + "USDT")
        else:
            # last-ditch: look for BTCUSDT-like token in the URL
            m = re.search(r"([A-Z]{2,10}[-_/]?(USDT|USDC|USD|BTC|ETH))", raw, re.I)
            if not m:
                raise ValueError("نتوانستم نماد ارز را از این آدرس استخراج کنم. نماد را دستی بنویسید (مثلاً BTCUSDT).")
            token = _normalize_pair_token(m.group(1))
    else:
        compact = raw.replace("\u200c", "").strip().lower()
        compact_nospace = compact.replace(" ", "").replace("-", "").replace("/", "")
        if compact in COIN_ALIASES:
            source_kind = "name"
            token = COIN_ALIASES[compact]
        elif compact_nospace in COIN_ALIASES:
            source_kind = "name"
            token = COIN_ALIASES[compact_nospace]
        elif re.match(r"^[A-Za-z]{2,15}:[A-Za-z0-9._\-]+$", raw.strip()):
            preferred, token = _from_tv_symbol(raw.strip())
            source_kind = "symbol"
        else:
            token = _normalize_pair_token(raw)
            if token.lower() in COIN_ALIASES:
                source_kind = "name"
                token = COIN_ALIASES[token.lower()]

    if not token:
        raise ValueError("نماد ارز شناسایی نشد.")

    token = token.upper()
    if token.endswith("PERP"):
        token = token[: -4]
    if not any(token.endswith(q) for q in QUOTE_ASSETS):
        if token.lower() in COIN_ALIASES:
            token = COIN_ALIASES[token.lower()]
        else:
            token = token + "USDT"

    base, quote = _split_base_quote(token)
    if not base or len(base) < 2:
        raise ValueError(f"نماد «{raw}» معتبر نیست.")

    return ParsedQuery(
        raw=raw,
        symbol=base + quote,
        base=base,
        quote=quote,
        preferred_exchange=preferred,
        source_kind=source_kind,
    )
