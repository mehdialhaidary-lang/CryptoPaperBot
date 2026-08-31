import ccxt
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime, timezone

# =========================================================
# 1. إعدادات البوت والنموذج (Configuration)
# =========================================================
CONFIG = {
    'symbol': 'BTC/USDT',
    'timeframe': '4h',
    'donchian_entry_period': 20,
    'donchian_exit_period': 10,
    'daily_ema': 50,
    'atr_period': 14,
    'atr_sl_mult': 2.0,
    'risk_pct': 0.015,          # 1.5% مخاطرة لكل صفقة
    'commission_pct': 0.001,    # 0.1% عمولة التداول
    'slippage_pct': 0.0005,      # 0.05% انزلاق سعري افتراضي
    'initial_balance': 1000.0,   # الرصيد الافتراضي الابتدائي ($)
    'state_file': 'paper_state_donchian.json',
    'poll_interval_sec': 60      # الفحص كل دقيقة
}

exchange = ccxt.binance({'enableRateLimit': True, 'timeout': 20000})

# =========================================================
# 2. إدارة حالة المحفظة والملفات (State Management)
# =========================================================
def load_state():
    default_state = {
        'balance': CONFIG['initial_balance'],
        'position': None,
        'trade_history': [],
        'last_processed_candle': None
    }
    if os.path.exists(CONFIG['state_file']):
        try:
            with open(CONFIG['state_file'], 'r', encoding='utf-8') as f:
                state = json.load(f)
                # دمج المفاتيح المفقودة في حال كان الملف قديماً
                for key, val in default_state.items():
                    if key not in state:
                        state[key] = val
                return state
        except Exception:
            pass
    return default_state

def save_state(state):
    with open(CONFIG['state_file'], 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4)

# =========================================================
# 3. جلب وتحليل البيانات (Data Fetching & Indicators)
# =========================================================
def fetch_data():
    ohlcv_4h = exchange.fetch_ohlcv(CONFIG['symbol'], timeframe=CONFIG['timeframe'], limit=100)
    df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms', utc=True)

    ohlcv_1d = exchange.fetch_ohlcv(CONFIG['symbol'], timeframe='1d', limit=100)
    df_1d = pd.DataFrame(ohlcv_1d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms', utc=True)

    df_1d['ema_daily'] = df_1d['close'].ewm(span=CONFIG['daily_ema'], adjust=False).mean()
    df_1d['daily_trend_up'] = df_1d['close'] > df_1d['ema_daily']
    df_1d['daily_date'] = df_1d['datetime'].dt.date

    df_4h['prev_daily_date'] = (df_4h['datetime'] - pd.Timedelta(days=1)).dt.date
    df = pd.merge(df_4h, df_1d[['daily_date', 'daily_trend_up']], left_on='prev_daily_date', right_on='daily_date', how='left')
    df['daily_trend_up'] = df['daily_trend_up'].ffill().fillna(False).astype(bool)

    df['donchian_high'] = df['high'].shift(1).rolling(window=CONFIG['donchian_entry_period']).max()
    df['donchian_low'] = df['low'].shift(1).rolling(window=CONFIG['donchian_exit_period']).min()

    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/CONFIG['atr_period'], adjust=False).mean()

    return df

# =========================================================
# 4. محرك التنفيذ اللحظي (Execution Engine)
# =========================================================
def run_bot_cycle():
    state = load_state()
    df = fetch_data()

    closed_candle = df.iloc[-2]
    current_candle = df.iloc[-1]
    candle_ts = int(closed_candle['timestamp'])

    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"[{now_str}] 🔍 فحص الشمعة | السعر الحالي: ${current_candle['close']:.2f} | الرصيد: ${state['balance']:.2f}")

    if state.get('last_processed_candle') == candle_ts and state['position'] is None:
        print("  ⏳ بانتظار إغلاق شمعة 4H جديدة...")
        return

    # 1. إدارة الصفقة المفتوحة
    if state['position'] is not None:
        pos = state['position']
        entry_price = pos['entry_price']
        sl = pos['sl']
        units = pos['units']

        hit_sl = current_candle['low'] <= sl
        break_exit = closed_candle['close'] < closed_candle['donchian_low']

        if hit_sl or break_exit:
            exit_price = sl if hit_sl else current_candle['open']
            reason = 'وقف الخسارة (ATR SL)' if hit_sl else 'إغلاق دونشيان (Donchian Exit)'
            
            effective_exit = exit_price * (1 - CONFIG['slippage_pct'])
            gross_pnl = (effective_exit - entry_price) * units
            fees = (entry_price * units * CONFIG['commission_pct']) + (effective_exit * units * CONFIG['commission_pct'])
            net_pnl = gross_pnl - fees
            pnl_pct = (net_pnl / state['balance']) * 100

            state['balance'] += net_pnl
            trade_record = {
                'entry_time': pos['entry_time'],
                'exit_time': str(current_candle['datetime']),
                'entry_price': entry_price,
                'exit_price': effective_exit,
                'pnl_usd': net_pnl,
                'pnl_pct': pnl_pct,
                'reason': reason,
                'final_balance': state['balance']
            }

            state['trade_history'].append(trade_record)
            state['position'] = None
            save_state(state)

            print(f"🚨 [إغلاق صفقة] السبب: {reason}")
            print(f"   سعر الخروج: ${effective_exit:.2f} | الربح/الخسارة: ${net_pnl:+.2f} ({pnl_pct:+.2f}%)")
            print(f"   الرصيد الجديد: ${state['balance']:.2f}\n")
            return

    # 2. البحث عن فرصة دخول جديدة
    if state['position'] is None and state.get('last_processed_candle') != candle_ts:
        breakout_up = closed_candle['close'] > closed_candle['donchian_high']
        daily_ok = bool(closed_candle['daily_trend_up'])

        if breakout_up and daily_ok:
            raw_entry = current_candle['open']
            entry_price = raw_entry * (1 + CONFIG['slippage_pct'])

            stop_dist = closed_candle['atr'] * CONFIG['atr_sl_mult']
            risk_amt = state['balance'] * CONFIG['risk_pct']
            units = risk_amt / stop_dist
            sl_price = entry_price - stop_dist

            state['position'] = {
                'entry_time': str(current_candle['datetime']),
                'entry_price': entry_price,
                'sl': sl_price,
                'units': units,
                'atr': closed_candle['atr']
            }
            state['last_processed_candle'] = candle_ts
            save_state(state)

            print(f"🚀 [دخول صفقة جديدة] اختراق دونشيان 20 أعلى الشمعة + الاتجاه اليومي صاعد!")
            print(f"   سعر الدخول المقدر: ${entry_price:.2f}")
            print(f"   وقف الخسارة (SL):   ${sl_price:.2f} (مسافة: ${stop_dist:.2f})")
            print(f"   حجم المركز (Units): {units:.4f} BTC")
            print(f"   المخاطرة المحددة:   ${risk_amt:.2f} ({CONFIG['risk_pct']*100:.1f}%)\n")
        else:
            state['last_processed_candle'] = candle_ts
            save_state(state)

# =========================================================
# 5. الحلقة الرئيسية للتشغيل (Main Loop)
# =========================================================
if __name__ == "__main__":
    print("=" * 65)
    print(" 🤖 بدء تشغيل بوت التداول الافتراضي (Crypto Paper Trading Bot)")
    print(f"  • الزوج: {CONFIG['symbol']} | الفريم: {CONFIG['timeframe']}")
    print(f"  • الرصيد الابتدائي: ${CONFIG['initial_balance']:.2f}")
    print(f"  • حجم المخاطرة: {CONFIG['risk_pct']*100}% لكل صفقة")
    print("=" * 65 + "\n")

    while True:
        try:
            run_bot_cycle()
        except Exception as e:
            print(f"⚠️ خطأ أثناء الفحص: {e}")
        time.sleep(CONFIG['poll_interval_sec'])