# SmartFlow

تحلیل تکنیکال + اسمارت‌مانی روی **شش تایم‌فریم**:

| تایم | وزن در امتیاز کلی |
| --- | --- |
| ۴ ساعته | ۳۲٪ |
| ۱ ساعته | ۲۴٪ |
| ۳۰ دقیقه | ۱۶٪ |
| ۱۵ دقیقه | ۱۲٪ |
| ۵ دقیقه | ۱۰٪ |
| ۱ دقیقه | ۶٪ |

ورودی: نماد (`BTCUSDT`، `بیتکوین`)، `BINANCE:ETHUSDT`، یا لینک تریدینگ‌ویو:

```
https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT
```

## فایل‌های پروژه

```
crypto_smc/
  start.bat          اجرا در ویندوز (پنجره باز می‌ماند)
  launch.py          راه‌انداز پایتون برای ویندوز
  app.py             سرور وب FastAPI
  requirements.txt
  analyzer/          موتور داده، SMC، تکنیکال، گزارش
  static/
    index.html       رابط
    styles.css       ظاهر رنگی
    app.js           چارت، زوم، رفرش ۲ دقیقه‌ای
```

## امکانات رابط

- چارت با لایه‌های FVG / اردر بلاک / BOS / CHoCH
- زوم با اسکرول موس، جابه‌جایی با درگ، دابل‌کلیک برای نمای کامل
- رفرش خودکار هر ۲ دقیقه روی همان ارز + دکمه «الان تازه کن»
- راهنمای اصطلاحات پایین صفحه (OB، FVG، امتیاز وزنی، BSL/SSL، …)

## اجرا در ویندوز

۱. کل پوشه `crypto_smc` را کپی کنید (نه فقط `start.bat`).  
۲. روی `start.bat` دوبار کلیک کنید. پنجره باید **باز بماند**.  
۳. مرورگر می‌رود روی `http://127.0.0.1:8000`

اگر پنجره یک لحظه باز شد و بسته شد:

1. Python را از [python.org](https://www.python.org/downloads/) نصب کنید و تیک **Add python.exe to PATH** را بزنید.
2. همه پنجره‌های cmd را ببندید و دوباره `start.bat` را بزنید.
3. یا در پوشه `crypto_smc` در نوار آدرس بنویسید `cmd` و بعد:

```bat
python launch.py
```

## اجرا دستی

```bash
cd crypto_smc
pip install -r requirements.txt
python app.py
```

خروجی متنی:

```bash
python app.py BTCUSDT
```

## چه چیزی محاسبه می‌شود؟

**اسمارت‌مانی:** ساختار HH/HL، BOS و CHoCH، اردر بلاک و بریکر، FVG، نقدینگی BSL/SSL، سقف و کف برابر، سوئیپ، پرمیوم/دیسکانت/OTE، Displacement.

**تکنیکال:** RSI، MACD، Stochastic، EMA ۹/۲۱/۵۰/۲۰۰، ATR، ADX، Bollinger، VWAP، واگرایی RSI.

داده از API عمومی صرافی‌ها می‌آید (Binance.US، MEXC، OKX، Bitget، …). کلید API لازم نیست.

> خروجی آموزشی است و توصیهٔ سرمایه‌گذاری نیست.
> سرمایه شما همیشه در معرض نابودی است. مسئولیت هرگونه استفاده با شخص معامله‌گر می‌باشد.

برنامه‌نویس: مهراد چناقچی — Instagram: [mehrad_chenaghchi_1990](https://instagram.com/mehrad_chenaghchi_1990) — [mehrad.chenaghchi@gmail.com](mailto:mehrad.chenaghchi@gmail.com) — 09355277636
