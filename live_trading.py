"""
================================================
 🔴 LIVE TRADING ENGINE — غير مفعّل بعد
================================================
هذا الملف جاهز للتداول الحقيقي على Binance.
لتفعيله:
  1. أضف BINANCE_API_KEY و BINANCE_API_SECRET في GitHub Secrets
  2. غيّر DRY_RUN = False
  3. تأكد أن لديك رصيداً كافياً في محفظة Binance Spot
  4. ابدأ بمبلغ صغير ($100-200) للاختبار الفعلي
================================================
"""
import os, sys, json, time, logging
from datetime import datetime, timezone
import ccxt
import urllib.request, urllib.parse

# =========================================================
# ⚠️ مفتاح الأمان الرئيسي — اجعله True للتداول الحقيقي
# =========================================================
DRY_RUN = True   # False = تداول حقيقي بالمال الفعلي!

TELEGRAM_TOKEN   = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
BINANCE_API_KEY  = os.getenv('BINANCE_API_KEY', '')
BINANCE_SECRET   = os.getenv('BINANCE_API_SECRET', '')

LIVE_CONFIG = {
    'BTC/USDT': {
        'fast_ema': 8, 'slow_ema': 30, 'rsi_period': 14,
        'atr_period': 14, 'atr_mult': 2.0, 'rr_ratio': 2.5,
        'risk_pct': 0.01,        # 1% مخاطرة فقط في الحياة الحقيقية (أقل من Paper)
        'min_order_usdt': 10.0,  # الحد الأدنى لأمر Binance
    },
    'ETH/USDT': {
        'fast_ema': 8, 'slow_ema': 30, 'rsi_period': 14,
        'atr_period': 14, 'atr_mult': 2.0, 'rr_ratio': 2.5,
        'risk_pct': 0.01,
        'min_order_usdt': 10.0,
    },
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [LIVE] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('live_trading.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def send_telegram(msg):
    if not TELEGRAM_TOKEN: return
    try:
        url  = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
        data = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}).encode()
        urllib.request.urlopen(urllib.request.Request(url, data), timeout=10)
    except Exception as e:
        logging.error(f'Telegram error: {e}')

def create_live_exchange():
    """إنشاء Exchange متصل بحساب Binance الحقيقي."""
    if not BINANCE_API_KEY or not BINANCE_SECRET:
        raise ValueError("❌ BINANCE_API_KEY و BINANCE_API_SECRET غير موجودان في المتغيرات البيئية!")
    return ccxt.binance({
        'apiKey': BINANCE_API_KEY,
        'secret': BINANCE_SECRET,
        'enableRateLimit': True,
        'timeout': 20000,
        'options': {'defaultType': 'spot'},
    })

def get_usdt_balance(exchange) -> float:
    """جلب رصيد USDT المتاح."""
    balance = exchange.fetch_balance()
    return float(balance['USDT']['free'])

def place_market_buy(exchange, symbol: str, usdt_amount: float) -> dict:
    """تنفيذ أمر شراء بالسوق."""
    if DRY_RUN:
        logging.info(f"[DRY RUN] سيتم شراء ${usdt_amount:.2f} من {symbol}")
        return {'status': 'dry_run', 'amount': usdt_amount}
    ticker = exchange.fetch_ticker(symbol)
    price  = ticker['last']
    qty    = usdt_amount / price
    # تقريب الكمية حسب精度 Binance
    market = exchange.market(symbol)
    qty    = exchange.amount_to_precision(symbol, qty)
    order  = exchange.create_market_buy_order(symbol, float(qty))
    logging.info(f"✅ أمر شراء منفّذ: {order}")
    return order

def place_market_sell(exchange, symbol: str, qty: float) -> dict:
    """تنفيذ أمر بيع بالسوق."""
    if DRY_RUN:
        logging.info(f"[DRY RUN] سيتم بيع {qty:.6f} من {symbol}")
        return {'status': 'dry_run', 'qty': qty}
    qty   = exchange.amount_to_precision(symbol, qty)
    order = exchange.create_market_sell_order(symbol, float(qty))
    logging.info(f"✅ أمر بيع منفّذ: {order}")
    return order

def get_live_state_file(symbol: str) -> str:
    return f"live_state_{symbol.replace('/','_')}.json"

def load_live_state(symbol: str) -> dict:
    f = get_live_state_file(symbol)
    if os.path.exists(f):
        with open(f) as fp:
            return json.load(fp)
    return {'position': None, 'trades': [], 'last_candle_time': 0}

def save_live_state(state: dict, symbol: str):
    f   = get_live_state_file(symbol)
    tmp = f + '.tmp'
    with open(tmp, 'w') as fp:
        json.dump(state, fp, indent=4, default=str)
    os.replace(tmp, f)

def check_and_execute(exchange, symbol: str):
    """دورة كاملة لزوج واحد — Live."""
    from paper_trading import fetch_strict_data, get_config
    cfg   = LIVE_CONFIG.get(symbol, {})
    state = load_live_state(symbol)
    df    = fetch_strict_data(exchange, symbol)
    if len(df) < 50: return

    closed = df.iloc[-2]
    prev   = df.iloc[-3]
    candle_time = int(closed['timestamp'])
    if candle_time <= state.get('last_candle_time', 0): return
    state['last_candle_time'] = candle_time

    # --- فحص إغلاق الصفقة المفتوحة ---
    pos = state.get('position')
    if pos:
        ticker = exchange.fetch_ticker(symbol)
        price  = ticker['last']
        if price <= pos['sl'] or price >= pos['tp']:
            reason = 'STOP_LOSS' if price <= pos['sl'] else 'TAKE_PROFIT'
            order  = place_market_sell(exchange, symbol, pos['qty'])
            pnl    = (price - pos['entry_price']) * pos['qty']
            state['trades'].append({
                'entry': pos['entry_price'], 'exit': price,
                'pnl': pnl, 'reason': reason,
                'time': str(datetime.now(timezone.utc))
            })
            state['position'] = None
            save_live_state(state, symbol)
            send_telegram(f"🔴 *LIVE إغلاق — {symbol}*\nالسبب: {reason} | ر/خ: `${pnl:+.2f}`")
            return

    # --- فحص إشارة دخول ---
    if not state.get('position'):
        cross_up = (prev['ema_fast'] <= prev['ema_slow']) and (closed['ema_fast'] > closed['ema_slow'])
        daily_up = bool(closed['daily_trend_up'])
        rsi_ok   = closed['rsi'] >= 40
        if cross_up and daily_up and rsi_ok:
            usdt_bal  = get_usdt_balance(exchange)
            risk_usdt = usdt_bal * cfg.get('risk_pct', 0.01)
            if risk_usdt < cfg.get('min_order_usdt', 10):
                logging.warning(f"[{symbol}] الرصيد غير كافٍ للدخول.")
                return
            ticker = exchange.fetch_ticker(symbol)
            price  = ticker['last']
            order  = place_market_buy(exchange, symbol, risk_usdt)
            qty    = risk_usdt / price
            atr    = closed['atr']
            state['position'] = {
                'entry_price': price,
                'sl': price - atr * cfg.get('atr_mult', 2.0),
                'tp': price + atr * cfg.get('atr_mult', 2.0) * cfg.get('rr_ratio', 2.5),
                'qty': qty,
                'time': str(datetime.now(timezone.utc))
            }
            save_live_state(state, symbol)
            send_telegram(
                f"🚀 *LIVE دخول صفقة — {symbol}*\n"
                f"السعر: `${price:,.2f}` | SL: `${state['position']['sl']:,.2f}` | TP: `${state['position']['tp']:,.2f}`\n"
                f"{'⚠️ DRY RUN — لا تداول فعلي' if DRY_RUN else '✅ تداول حقيقي منفّذ!'}"
            )

def main():
    if DRY_RUN:
        logging.info("⚠️  وضع DRY RUN — لا يوجد تداول حقيقي")
        send_telegram("⚠️ *Live Bot — DRY RUN MODE*\nلن يتم تنفيذ أي أوامر حقيقية.")
    else:
        logging.info("🔴 وضع LIVE TRADING — التداول الحقيقي مفعّل!")
        send_telegram("🔴 *Live Bot — LIVE MODE مفعّل!*\nسيتم تنفيذ أوامر حقيقية.")

    exchange = create_live_exchange()

    for symbol in LIVE_CONFIG:
        try:
            check_and_execute(exchange, symbol)
        except Exception as e:
            logging.error(f"[{symbol}] خطأ: {e}", exc_info=True)
            send_telegram(f"🚨 LIVE خطأ في {symbol}: `{e}`")

if __name__ == '__main__':
    main()