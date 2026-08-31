import os
import sys
import json
import time
import logging
from datetime import datetime, timezone
import ccxt
import pandas as pd
import numpy as np
import urllib.request
import urllib.parse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =========================================================
# 🔒 البيانات الحساسة والإعدادات
# =========================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ضع_التوكن_هنا")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

STATE_FILE = 'paper_state.json'
LOCK_FILE = 'paper_bot.lock'

CONFIG = {
    'symbol': 'BTC/USDT',
    'timeframe': '4h',
    'fast_ema': 8,
    'slow_ema': 30,
    'rsi_period': 14,
    'atr_period': 14,
    'atr_mult': 2.0,
    'rr_ratio': 2.5,
    'risk_pct': 0.02,
    # التكاليف الواقعية
    'commission_pct': 0.001,   # 0.1% عمولة منصة
    'slippage_pct': 0.0005,    # 0.05% انزلاق سعري
    'spread_pct': 0.0002,      # 0.02% فارق العرض والطلب
    'initial_balance': 1000.0,
    'heartbeat_interval_hours': 6  # إرسال نبضة حياة عبر تلغرام كل كم ساعة
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def is_process_alive(pid):
    if pid <= 0:
        return False
    if os.name == 'posix':
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
    import ctypes
    kernel32 = ctypes.windll.kernel32
    SYNCHRONIZE = 0x00100000
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    return False

def prevent_multiple_instances():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            if is_process_alive(old_pid):
                logging.error(f"❌ يوجد نسخة أخرى تعمل بالفعل (PID: {old_pid})! تم إيقاف التشغيل.")
                sys.exit(1)
            logging.warning(f"🔒 ملف قفل قديم من عملية منتهية (PID: {old_pid}) — سيتم تجاوزه.")
        except ValueError:
            logging.warning("⚠️ ملف قفل تالف — سيتم إعادة إنشائه.")
        except OSError as e:
            logging.warning(f"⚠️ تعذر قراءة ملف القفل ({e}) — سيتم إعادة إنشائه.")
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

def release_instance_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def send_telegram(message):
    if "ضع_التوكن" in TELEGRAM_TOKEN or not TELEGRAM_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            'chat_id': TELEGRAM_CHAT_ID, 
            'text': message, 
            'parse_mode': 'Markdown'
        }).encode('utf-8')
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logging.error(f"⚠️ فشل إرسال إشعار تلغرام: {e}")

def send_heartbeat(state, start_time):
    uptime_hours = (time.time() - start_time) / 3600
    if state['position'] is None:
        pos_status = "لا توجد صفقة مفتوحة"
    else:
        pos_status = f"صفقة مفتوحة @ ${state['position']['entry_price']:,.2f}"

    msg = (
        f"💓 *نبضة حياة (Heartbeat)*\n\n"
        f"✅ البوت يعمل بشكل طبيعي\n"
        f"⏱️ مدة التشغيل المتواصل: {uptime_hours:.1f} ساعة\n"
        f"💰 الرصيد الحالي: `${state['balance']:,.2f}`\n"
        f"📍 الحالة: {pos_status}\n"
        f"🔄 عدد الصفقات المغلقة: {len(state['trades'])}"
    )
    send_telegram(msg)
    logging.info(f"💓 تم إرسال نبضة حياة (uptime: {uptime_hours:.1f}h)")

def calc_wilder_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def fetch_strict_data(exchange):
    """جلب البيانات وربط اليومي بتاريخ اليوم السابق UTC صراحة لمنع التسريب 100%"""
    ohlcv_4h = exchange.fetch_ohlcv(CONFIG['symbol'], timeframe='4h', limit=300)
    ohlcv_1d = exchange.fetch_ohlcv(CONFIG['symbol'], timeframe='1d', limit=150)

    df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df_1d = pd.DataFrame(ohlcv_1d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms', utc=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms', utc=True)

    # حساب الاتجاه اليومي للشمعة المكتملة
    df_1d['ema_21_1d'] = df_1d['close'].ewm(span=21, adjust=False).mean()
    df_1d['daily_trend_up'] = df_1d['close'] > df_1d['ema_21_1d']
    df_1d['daily_date'] = df_1d['datetime'].dt.date

    # ربط شمعة الـ 4H بـ (تاريخ اليوم السابق UTC) حكماً
    df_4h['prev_daily_date'] = (df_4h['datetime'] - pd.Timedelta(days=1)).dt.date

    df = pd.merge(
        df_4h,
        df_1d[['daily_date', 'daily_trend_up']],
        left_on='prev_daily_date',
        right_on='daily_date',
        how='left'
    )
    df['daily_trend_up'] = df['daily_trend_up'].ffill().fillna(False).astype(bool)

    # حساب المؤشرات الفنية للـ 4h
    df['ema_fast'] = df['close'].ewm(span=CONFIG['fast_ema'], adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=CONFIG['slow_ema'], adjust=False).mean()

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/CONFIG['rsi_period'], adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/CONFIG['rsi_period'], adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))

    df['atr'] = calc_wilder_atr(df, period=CONFIG['atr_period'])

    return df

def calculate_advanced_metrics(trades, initial_balance):
    if not trades:
        return {}
    df_t = pd.DataFrame(trades)
    pnls = df_t['pnl'].values
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    win_rate = (len(wins) / len(trades)) * 100 if len(trades) > 0 else 0
    gross_profit = wins.sum() if len(wins) > 0 else 0
    gross_loss = abs(losses.sum()) if len(losses) > 0 else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else np.inf
    
    balances = [initial_balance] + df_t['balance_after'].tolist()
    peak = balances[0]
    max_dd = 0
    for b in balances:
        if b > peak:
            peak = b
        dd = (peak - b) / peak
        if dd > max_dd:
            max_dd = dd

    return {
        'total_trades': len(trades),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_drawdown_pct': max_dd * 100
    }

def load_state():
    defaults = {
        'balance': CONFIG['initial_balance'],
        'initial_balance': CONFIG['initial_balance'],
        'position': None,
        'last_processed_candle_time': 0,
        'trades': []
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                saved = json.load(f)
            if not isinstance(saved, dict):
                raise ValueError("صيغة ملف الحالة غير صالحة")
            if 'trades' not in saved and 'trade_history' in saved:
                saved['trades'] = []
            for key, val in defaults.items():
                saved.setdefault(key, val)
            return saved
        except Exception as e:
            logging.warning(f"⚠️ تعذر قراءة ملف الحالة ({e}) — سيتم إنشاء حالة جديدة.")
    return defaults

def save_state(state):
    tmp_file = STATE_FILE + '.tmp'
    with open(tmp_file, 'w') as f:
        json.dump(state, f, indent=4, default=str)
    os.replace(tmp_file, STATE_FILE)

# =========================================================
# ⚡ 1. مراقب الصفقات اللحظي (Position Monitor)
# =========================================================
def monitor_live_position(exchange, state):
    pos = state['position']
    if pos is None:
        return

    ticker = exchange.fetch_ticker(CONFIG['symbol'])
    current_price = ticker['last']

    entry_price = pos['entry_price']
    sl, tp, units = pos['sl'], pos['tp'], pos['units']

    exit_price = None
    exit_reason = None

    if current_price <= sl:
        exit_price = sl
        exit_reason = 'STOP LOSS 🔴 (Live Hit)'
    elif current_price >= tp:
        exit_price = tp
        exit_reason = 'TAKE PROFIT 🟢 (Live Hit)'

    if exit_price:
        effective_exit = exit_price * (1 - CONFIG['slippage_pct'] - CONFIG['spread_pct'])
        gross_pnl = (effective_exit - entry_price) * units
        total_fees = (entry_price * units * CONFIG['commission_pct']) + (effective_exit * units * CONFIG['commission_pct'])
        net_pnl = gross_pnl - total_fees

        state['balance'] += net_pnl
        
        trade_log = {
            'entry_time': pos['entry_time'],
            'exit_time': str(datetime.now(timezone.utc)),
            'entry_price': entry_price,
            'exit_price': effective_exit,
            'pnl': net_pnl,
            'reason': exit_reason,
            'balance_after': state['balance']
        }
        state['trades'].append(trade_log)
        state['position'] = None
        save_state(state)

        metrics = calculate_advanced_metrics(state['trades'], state['initial_balance'])
        
        msg = (
            f"🚨 *إغلاق صفقة محاكاة (تنفيذ لحظي)*\n\n"
            f"📌 *الزوج:* `{CONFIG['symbol']}`\n"
            f"🎯 *السبب:* {exit_reason}\n"
            f"💵 *سعر الخروج:* `${effective_exit:,.2f}`\n"
            f"📈 *صافي الربح/الخسارة:* `${net_pnl:+.2f}`\n"
            f"💰 *الرصيد الجديد:* `${state['balance']:,.2f}`\n\n"
            f"📊 *الإحصائيات الحالية:*\n"
            f"• Win Rate: `{metrics.get('win_rate', 0):.1f}%`\n"
            f"• Profit Factor: `{metrics.get('profit_factor', 0):.2f}`\n"
            f"• Max Drawdown: `{metrics.get('max_drawdown_pct', 0):.2f}%`"
        )
        send_telegram(msg)
        logging.info(f"🚨 إغلاق لحظي للصفقة: {exit_reason} عند سعر ${effective_exit:,.2f}")

# =========================================================
# 🧠 2. محرك الإشارات على الشموع المغلقة (Signal Engine)
# =========================================================
def evaluate_signals_on_candle_close(exchange, state):
    df = fetch_strict_data(exchange)
    if df is None or len(df) < 50:
        return

    closed_candle = df.iloc[-2]
    prev_closed_candle = df.iloc[-3]
    candle_time = int(closed_candle['timestamp'])

    if candle_time <= state.get('last_processed_candle_time', 0):
        return

    state['last_processed_candle_time'] = candle_time
    save_state(state)

    logging.info(
        f"📊 [شمعة جديدة مغلقة] [{closed_candle['datetime']}] | Close: ${closed_candle['close']:,.2f} | "
        f"Fast EMA: {closed_candle['ema_fast']:.2f} | Slow EMA: {closed_candle['ema_slow']:.2f} | "
        f"RSI: {closed_candle['rsi']:.1f} | ATR: {closed_candle['atr']:.2f} | Daily Trend Up: {closed_candle['daily_trend_up']}"
    )

    pos = state['position']

    if pos is not None:
        if (prev_closed_candle['ema_fast'] >= prev_closed_candle['ema_slow']) and (closed_candle['ema_fast'] < closed_candle['ema_slow']):
            entry_price = pos['entry_price']
            units = pos['units']
            ticker_now = exchange.fetch_ticker(CONFIG['symbol'])
            exit_price = ticker_now['last']
            
            effective_exit = exit_price * (1 - CONFIG['slippage_pct'] - CONFIG['spread_pct'])
            gross_pnl = (effective_exit - entry_price) * units
            total_fees = (entry_price * units * CONFIG['commission_pct']) + (effective_exit * units * CONFIG['commission_pct'])
            net_pnl = gross_pnl - total_fees

            state['balance'] += net_pnl
            state['trades'].append({
                'entry_time': pos['entry_time'],
                'exit_time': str(closed_candle['datetime']),
                'entry_price': entry_price,
                'exit_price': effective_exit,
                'pnl': net_pnl,
                'reason': 'REVERSE SIGNAL 🔄',
                'balance_after': state['balance']
            })
            state['position'] = None
            save_state(state)
            send_telegram(f"🔄 إغلاق صفقة بسبب تقاطع عكسي عند سعر `${effective_exit:,.2f}`")

    if state['position'] is None:
        cross_up = (prev_closed_candle['ema_fast'] <= prev_closed_candle['ema_slow']) and (closed_candle['ema_fast'] > closed_candle['ema_slow'])
        daily_up = bool(closed_candle['daily_trend_up'])
        rsi_ok = closed_candle['rsi'] >= 40

        if cross_up and daily_up and rsi_ok:
            ticker = exchange.fetch_ticker(CONFIG['symbol'])
            raw_entry = ticker['last']
            entry_price = raw_entry * (1 + CONFIG['slippage_pct'] + CONFIG['spread_pct'])

            atr = closed_candle['atr']
            stop_dist = atr * CONFIG['atr_mult']
            risk_amt = state['balance'] * CONFIG['risk_pct']
            units = risk_amt / stop_dist
            max_units = state['balance'] / entry_price
            if units > max_units:
                units = max_units
                logging.warning("⚠️ تم تقييد حجم المركز بالرصيد المتاح لمنع رافعة ضمنية.")

            state['position'] = {
                'entry_time': str(datetime.now(timezone.utc)),
                'entry_price': entry_price,
                'sl': entry_price - stop_dist,
                'tp': entry_price + (stop_dist * CONFIG['rr_ratio']),
                'units': units
            }
            save_state(state)

            msg = (
                f"🚀 *دخول صفقة جديدة (تنفيذ لحظي عند الشمعة الجديدة)*\n\n"
                f"📌 *الزوج:* `{CONFIG['symbol']}`\n"
                f"💵 *سعر الدخول:* `${entry_price:,.2f}`\n"
                f"🔴 *وقف الخسارة (SL):* `${entry_price - stop_dist:,.2f}`\n"
                f"🟢 *جني الأرباح (TP):* `${entry_price + (stop_dist * CONFIG['rr_ratio']):,.2f}`\n"
                f"📊 *الكمية:* `{units:.4f}`"
            )
            send_telegram(msg)
            logging.info(f"🚀 فتح صفقة جديدة عند السعر ${entry_price:,.2f}")

def main():
    prevent_multiple_instances()
    try:
        state = load_state()

        # 🛠️ التهيئة الصحيحة لـ CCXT لمنع الاتصال بـ dapi وزيادة timeout
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'timeout': 20000,  # 20 ثانية مهلة اتصال
            'options': {
                'defaultType': 'spot',
                'fetchMarkets': ['spot']  # إلغاء طلب أسواق dapi/fapi لتجنب الـ Timeout
            }
        })
        
        logging.info("=" * 60)
        logging.info("🤖 تشغيل محاكي التداول الكمّي (Paper Trading Engine)...")
        logging.info(f"💰 الرصيد الحالي: ${state['balance']:.2f}")
        logging.info("=" * 60)

        start_time = time.time()
        last_heartbeat = start_time
        heartbeat_interval_sec = CONFIG['heartbeat_interval_hours'] * 3600
        send_heartbeat(state, start_time)

        while True:
            try:
                monitor_live_position(exchange, state)
                evaluate_signals_on_candle_close(exchange, state)

                if time.time() - last_heartbeat >= heartbeat_interval_sec:
                    send_heartbeat(state, start_time)
                    last_heartbeat = time.time()
            except (ccxt.RequestTimeout, ccxt.NetworkError) as ne:
                logging.warning(f"⚠️ انقطاع مؤقت في الشبكة/المنصة: {ne} (سيتم إعادة المحاولة بعد 10 ثوانٍ)")
            except Exception as e:
                logging.error(f"❌ خطأ غير متوقع أثناء الدورة: {e}", exc_info=True)

            time.sleep(10)
    finally:
        release_instance_lock()

if __name__ == "__main__":
    main()