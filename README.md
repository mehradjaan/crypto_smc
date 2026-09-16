# SmartFlow

**تحلیل تکنیکال + اسمارت‌مانی چند تایم‌فریمی برای ارزهای دیجیتال**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-web-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Educational-yellow)](#disclaimer--هشدار-ریسک)

نماد، نام فارسی ارز، یا لینک چارت تریدینگ‌ویو را بدهید؛ برنامه کندل زنده را از صرافی می‌گیرد و روی **شش تایم‌فریم** همزمان اسمارت‌مانی و تکنیکال را می‌خواند.

```
BTCUSDT
بیتکوین
BINANCE:ETHUSDT
https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT
```

> **هشدار:** این نرم‌افزار توصیه مالی یا سیگنال تضمینی نیست. سرمایه همیشه در معرض نابودی است. مسئولیت هر معامله فقط با خود معامله‌گر است.

---

## English

SmartFlow is a local web app for **crypto technical analysis + Smart Money Concepts (SMC)** across six timeframes (1m, 5m, 15m, 30m, 1h, 4h). Paste a symbol or a TradingView URL; it fetches public OHLCV (no API key) and returns structure, order blocks, FVGs, liquidity, classic indicators, and a weighted multi-TF bias.

**Not financial advice.** Use at your own risk.

### Quick start

```bash
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000)

Windows: double-click `start.bat` (Python must be on PATH).

CLI:

```bash
python app.py BTCUSDT
```

---

## امکانات

- شش تایم‌فریم: **۱ دقیقه · ۵ دقیقه · ۱۵ دقیقه · ۳۰ دقیقه · ۱ ساعته · ۴ ساعته**
- **اسمارت‌مانی:** ساختار HH/HL و LH/LL، BOS و CHoCH، اردر بلاک و بریکر، Fair Value Gap، نقدینگی BSL/SSL، سقف و کف برابر، سوئیپ، پرمیوم / دیسکانت / OTE، Displacement
- **تکنیکال:** RSI، MACD، Stochastic، EMA ۹ / ۲۱ / ۵۰ / ۲۰۰، ATR، ADX، Bollinger، VWAP، واگرایی RSI
- هم‌گرایی وزنی تایم‌فریم‌ها + ناحیه تمرکز، باطل‌شدن نسبی و اهداف نقدینگی
- چارت تعاملی با لایه FVG و اردر بلاک — اسکرول موس برای زوم، درگ برای جابه‌جایی
- رفرش خودکار هر **۲ دقیقه** روی همان نماد
- راهنمای اصطلاحات داخل خود برنامه
- بدون کلید API — داده از API عمومی صرافی‌ها (Binance.US، MEXC، OKX، Bitget، …)

### وزن هم‌گرایی

| تایم‌فریم | وزن |
| --- | ---: |
| ۴ ساعته | ۳۲٪ |
| ۱ ساعته | ۲۴٪ |
| ۳۰ دقیقه | ۱۶٪ |
| ۱۵ دقیقه | ۱۲٪ |
| ۵ دقیقه | ۱۰٪ |
| ۱ دقیقه | ۶٪ |

تایم بالاتر اولویت دارد؛ ۱ دقیقه به‌تنهایی مبنای تصمیم نیست.

---

## نصب و اجرا

### پیش‌نیاز

- [Python 3.10+](https://www.python.org/downloads/)
- در ویندوز هنگام نصب، تیک **Add python.exe to PATH** را بزنید

### ویندوز

1. مخزن را Clone یا دانلود کنید
2. وارد پوشه پروژه شوید
3. روی `start.bat` دوبار کلیک کنید — پنجره باید باز بماند
4. مرورگر روی `http://127.0.0.1:8000` باز می‌شود

اگر پنجره فوری بسته شد، Python در PATH نیست. بعد از نصب پایتون، همه پنجره‌های cmd را ببندید و دوباره امتحان کنید، یا:

```bat
python launch.py
```

### لینوکس / مک

```bash
git clone https://github.com/<USER>/<REPO>.git
cd <REPO>
pip install -r requirements.txt
python app.py
```

سپس [http://127.0.0.1:8000](http://127.0.0.1:8000) را باز کنید.

خروجی متنی در ترمینال:

```bash
python app.py BTCUSDT
python app.py "https://www.tradingview.com/chart/?symbol=BINANCE:ETHUSDT"
```

---

## ساختار پروژه

```
├── app.py              # سرور FastAPI
├── launch.py           # راه‌انداز ویندوز
├── start.bat           # اجرای دابل‌کلیک در ویندوز
├── requirements.txt
├── analyzer/           # داده، SMC، تکنیکال، امتیازدهی، گزارش فارسی
│   ├── data.py
│   ├── parse.py
│   ├── smc.py
│   ├── ta.py
│   ├── report.py
│   └── pipeline.py
└── static/             # رابط وب
    ├── index.html
    ├── styles.css
    └── app.js
```

---

## نحوه استفاده

1. نماد را بنویسید (`BTCUSDT`، `ETH`، `سولانا`) یا لینک چارت را بچسبانید
2. دکمه **تحلیل** را بزنید
3. سوگیری کلی، چارت SMC، گزارش متنی و کارت هر تایم‌فریم را بخوانید
4. پایین صفحه معنی OB، FVG، BOS، امتیاز وزنی و بقیه اصطلاحات آمده است

اگر لینک تریدینگ‌ویو فقط شناسه چارت باشد و پارامتر `symbol` نداشته باشد، خود نماد را وارد کنید.

---

## Disclaimer / هشدار ریسک

تحلیل‌های این برنامه **صرفاً راهنما و آموزشی** هستند و توصیه سرمایه‌گذاری، سیگنال خرید/فروش یا تضمین سود نیستند.

- سرمایه شما همیشه در معرض نابودی است
- مسئولیت هرگونه استفاده فقط با شخص معامله‌گر است
- به هیچ عنوان سرمایه‌ای را که توان از دست دادنش را ندارید وارد بازار نکنید
- ۱ دقیقه و ۵ دقیقه نویز بالایی دارند؛ اولویت با ۴ ساعته و ۱ ساعته است

---

## برنامه‌نویس

**مهراد چناقچی**

- Instagram: [mehrad_chenaghchi_1990](https://instagram.com/mehrad_chenaghchi_1990)
- Email: [mehrad.chenaghchi@gmail.com](mailto:mehrad.chenaghchi@gmail.com)
- Contact: [09355277636](tel:09355277636)

Contact me with 09355277636
