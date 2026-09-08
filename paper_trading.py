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
# 🔒 البيانات الحساسة
# =========================================================
TELEGRAM_TOKEN   = os.getenv('TELEGRAM_TOKEN', 'ضع_التوكن_هنا')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# =========================================================
# ⚙️ إعدادات كل زوج
# =========================================================
SYMBOLS_CONFIG = {
    'BTC/USDT': {
        'timeframe': '4h', 'fast_ema': 8, 'slow_ema': 30,
        'rsi_period': 14, 'atr_period': 14, 'atr_mult': 2.0,
        'rr_ratio': 2.5, 'risk_pct': 0.02,
        'commission_pct': 0.001, 'slippage_pct': 0.0005, 'spread_pct': 0.0002,
        'initial_balance': 1000.0, 'heartbeat_interval_hours': 6,
    },
    'ETH/USDT': {
        'timeframe': '4h', 'fast_ema': 8, 'slow_ema': 30,
        'rsi_period': 14, 'atr_period': 14, 'atr_mult': 2.0,
        'rr_ratio': 2.5, 'risk_pct': 0.02,
        'commission_pct': 0.001, 'slippage_pct': 0.0005, 'spread_pct': 0.0002,
        'initial_balance': 1000.0, 'heartbeat_interval_hours': 6,
    },
}

CONFIG = SYMBOLS_CONFIG['BTC/USDT']
CONFIG['symbol'] = 'BTC/USDT'
LOCK_FILE = 'paper_bot.lock'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def get_config(symbol: str) -> dict:
    cfg = SYMBOLS_CONFIG.get(symbol, SYMBOLS_CONFIG['BTC/USDT']).copy()
    cfg['symbol'] = symbol
    return cfg

def get_state_file(symbol: str) -> str:
    return f"paper_state_{symbol.replace('/', '_')}.json"

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
    handle = kernel32.OpenProcess(0x00100000, False, pid)
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
                logging.error(f'❌ يوجد نسخة أخرى تعمل بالفعل (PID: {old_pid})!')
                sys.exit(1)
            logging.warning(f'🔒 ملف قفل قديم (PID: {old_pid}) — سيتم تجاوزه.')
        except (ValueError, OSError) as e:
            logging.warning(f'⚠️ ملف قفل تالف ({e}) — سيتم إعادة إنشائه.')
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

def release_instance_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def send_telegram(message: str):
    if 'ضع_التوكن' in TELEGRAM_TOKEN or not TELEGRAM_TOKEN:
        return
    try:
        url  = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
        data = urllib.parse.urlencode({
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }).encode('utf-8')
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception as e:
        logging.error(f'⚠️ فشل إرسال تلغرام: {e}')

def send_heartbeat(state: dict, start_time: float, symbol: str = 'BTC/USDT'):
    uptime_h   = (time.time() - start_time) / 3600
    pos        = state.get('position')
    pos_status = 'لا توجد صفقة مفتوحة' if pos is None else \
        f"صفقة مفتوحة @ ${pos['entry_price']:,.2f}"
    msg = (
        f'💓 *نبضة حياة — {symbol}*\n\n'
        f'✅ البوت يعمل بشكل طبيعي (تشغيل مجدوَل)\n'
        f'💰 الرصيد الحالي: `${state["balance"]:,.2f}`\n'
        f'📍 الحالة: {pos_status}\n'
        f'🔄 عدد الصفقات المغلقة: {len(state.get("trades", []))}'
    )
    send_telegram(msg)
    logging.info(f'💓 [{symbol}] نبضة حياة (uptime: {uptime_h:.1f}h)')

def load_state(symbol: str = 'BTC/USDT') -> dict:
    cfg        = get_config(symbol)
    state_file = get_state_file(symbol)
    defaults   = {
        'balance': cfg['initial_balance'],
        'initial_balance': cfg['initial_balance'],
        'position': None,
        'last_processed_candle_time': 0,
        'trades': [],
        'last_heartbeat_time': 0,
    }
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                saved = json.load(f)
            if not isinstance(saved, dict):
                raise ValueError('صيغة ملف الحالة غير صالحة')
            for key, val in defaults.items():
                saved.setdefault(key, val)
            return saved
        except Exception as e:
            logging.warning(f'⚠️ [{symbol}] تعذر قراءة ملف الحالة ({e}) — حالة جديدة.')
    return defaults

def save_state(state: dict, symbol: str = 'BTC/USDT'):
    state_file = get_state_file(symbol)
    tmp        = state_file + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=4, default=str)
    os.replace(tmp, state_file)

def calc_wilder_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low   = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close  = (df['low']  - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()

def fetch_strict_data(exchange, symbol: str = 'BTC/USDT') -> pd.DataFrame:
    cfg      = get_config(symbol)
    ohlcv_4h = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=300)
    ohlcv_1d = exchange.fetch_ohlcv(symbol, timeframe='1d', limit=150)
    df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp','open','high','low','close','volume'])
    df_1d = pd.DataFrame(ohlcv_1d, columns=['timestamp','open','high','low','close','volume'])
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms', utc=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms', utc=True)
    df_1d['ema_21_1d']      = df_1d['close'].ewm(span=21, adjust=False).mean()
    df_1d['daily_trend_up'] = df_1d['close'] > df_1d['ema_21_1d']
    df_1d['daily_date']     = df_1d['datetime'].dt.date
    df_4h['prev_daily_date'] = (df_4h['datetime'] - pd.Timedelta(days=1)).dt.date
    df = pd.merge(
        df_4h, df_1d[['daily_date','daily_trend_up']],
        left_on='prev_daily_date', right_on='daily_date', how='left'
    )
    df['daily_trend_up'] = df['daily_trend_up'].ffill().fillna(False).astype(bool)
    df['ema_fast'] = df['close'].ewm(span=cfg['fast_ema'], adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=cfg['slow_ema'], adjust=False).mean()
    delta = df['close'].diff()
    gain  = (delta.where(delta > 0, 0)).ewm(alpha=1/cfg['rsi_period'], adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0)).ewm(alpha=1/cfg['rsi_period'], adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    df['atr'] = calc_wilder_atr(df, period=cfg['atr_period'])
    return df

def calculate_advanced_metrics(trades: list, initial_balance: float) -> dict:
    if not trades:
        return {}
    df_t   = pd.DataFrame(trades)
    pnls   = df_t['pnl'].values
    wins   = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    win_rate      = (len(wins) / len(trades)) * 100
    gross_profit  = wins.sum()        if len(wins)   > 0 else 0
    gross_loss    = abs(losses.sum()) if len(losses) > 0 else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
    balances      = [initial_balance] + df_t['balance_after'].tolist()
    peak, max_dd  = balances[0], 0
    for b in balances:
        if b > peak: peak = b
        dd = (peak - b) / peak
        if dd > max_dd: max_dd = dd
    return {
        'total_trades': len(trades), 'win_rate': win_rate,
        'profit_factor': profit_factor, 'max_drawdown_pct': max_dd * 100,
    }

def monitor_live_position(exchange, state: dict, symbol: str = 'BTC/USDT'):
    cfg = get_config(symbol)
    pos = state.get('position')
    if pos is None:
        return
    ticker        = exchange.fetch_ticker(symbol)
    current_price = ticker['last']
    entry_price   = pos['entry_price']
    sl, tp, units = pos['sl'], pos['tp'], pos['units']
    exit_price, exit_reason = None, None
    if current_price <= sl:
        exit_price  = sl
        exit_reason = 'STOP LOSS 🔴 (Live Hit)'
    elif current_price >= tp:
        exit_price  = tp
        exit_reason = 'TAKE PROFIT 🟢 (Live Hit)'
    if exit_price is None:
        return
    effective_exit = exit_price * (1 - cfg['slippage_pct'] - cfg['spread_pct'])
    gross_pnl  = (effective_exit - entry_price) * units
    total_fees = (entry_price * units * cfg['commission_pct']) + \
                 (effective_exit * units * cfg['commission_pct'])
    net_pnl    = gross_pnl - total_fees
    state['balance'] += net_pnl
    state['trades'].append({
        'entry_time': pos['entry_time'], 'exit_time': str(datetime.now(timezone.utc)),
        'entry_price': entry_price, 'exit_price': effective_exit,
        'pnl': net_pnl, 'reason': exit_reason, 'balance_after': state['balance'],
    })
    state['position'] = None
    save_state(state, symbol)
    metrics = calculate_advanced_metrics(state['trades'], state['initial_balance'])
    send_telegram(
        f'🚨 *إغلاق صفقة — {symbol}*\n\n'
        f'🎯 *السبب:* {exit_reason}\n'
        f'💵 *سعر الخروج:* `${effective_exit:,.2f}`\n'
        f'📈 *صافي ر/خ:* `${net_pnl:+.2f}`\n'
        f'💰 *الرصيد الجديد:* `${state["balance"]:,.2f}`\n\n'
        f'📊 Win Rate: `{metrics.get("win_rate",0):.1f}%` | '
        f'PF: `{metrics.get("profit_factor",0):.2f}` | '
        f'DD: `{metrics.get("max_drawdown_pct",0):.2f}%`'
    )
    logging.info(f'🚨 [{symbol}] إغلاق لحظي: {exit_reason} @ ${effective_exit:,.2f}')

def evaluate_signals_on_candle_close(exchange, state: dict, symbol: str = 'BTC/USDT'):
    cfg = get_config(symbol)
    df  = fetch_strict_data(exchange, symbol)
    if df is None or len(df) < 50:
        return
    closed_candle      = df.iloc[-2]
    prev_closed_candle = df.iloc[-3]
    candle_time        = int(closed_candle['timestamp'])
    if candle_time <= state.get('last_processed_candle_time', 0):
        return
    state['last_processed_candle_time'] = candle_time
    save_state(state, symbol)
    logging.info(
        f'📊 [{symbol}] شمعة مغلقة [{closed_candle["datetime"]}] | '
        f'Close: ${closed_candle["close"]:,.2f} | '
        f'Fast EMA: {closed_candle["ema_fast"]:.2f} | '
        f'Slow EMA: {closed_candle["ema_slow"]:.2f} | '
        f'RSI: {closed_candle["rsi"]:.1f} | '
        f'ATR: {closed_candle["atr"]:.2f} | '
        f'Daily Trend Up: {closed_candle["daily_trend_up"]}'
    )
    pos = state.get('position')
    if pos is not None:
        cross_down = (prev_closed_candle['ema_fast'] >= prev_closed_candle['ema_slow']) and \
                     (closed_candle['ema_fast'] < closed_candle['ema_slow'])
        if cross_down:
            ticker   = exchange.fetch_ticker(symbol)
            eff_exit = ticker['last'] * (1 - cfg['slippage_pct'] - cfg['spread_pct'])
            gross    = (eff_exit - pos['entry_price']) * pos['units']
            fees     = (pos['entry_price'] * pos['units'] * cfg['commission_pct']) + \
                       (eff_exit * pos['units'] * cfg['commission_pct'])
            net_pnl  = gross - fees
            state['balance'] += net_pnl
            state['trades'].append({
                'entry_time': pos['entry_time'], 'exit_time': str(closed_candle['datetime']),
                'entry_price': pos['entry_price'], 'exit_price': eff_exit,
                'pnl': net_pnl, 'reason': 'REVERSE SIGNAL 🔄',
                'balance_after': state['balance'],
            })
            state['position'] = None
            save_state(state, symbol)
            send_telegram(
                f'🔄 *إغلاق بتقاطع عكسي — {symbol}*\n'
                f'سعر الخروج: `${eff_exit:,.2f}` | ر/خ: `${net_pnl:+.2f}`'
            )
    if state.get('position') is None:
        cross_up = (prev_closed_candle['ema_fast'] <= prev_closed_candle['ema_slow']) and \
                   (closed_candle['ema_fast'] > closed_candle['ema_slow'])
        daily_up = bool(closed_candle['daily_trend_up'])
        rsi_ok   = closed_candle['rsi'] >= 40
        if cross_up and daily_up and rsi_ok:
            ticker      = exchange.fetch_ticker(symbol)
            entry_price = ticker['last'] * (1 + cfg['slippage_pct'] + cfg['spread_pct'])
            atr         = closed_candle['atr']
            stop_dist   = atr * cfg['atr_mult']
            risk_amt    = state['balance'] * cfg['risk_pct']
            units       = min(risk_amt / stop_dist, state['balance'] / entry_price)
            state['position'] = {
                'entry_time':  str(datetime.now(timezone.utc)),
                'entry_price': entry_price,
                'sl':  entry_price - stop_dist,
                'tp':  entry_price + stop_dist * cfg['rr_ratio'],
                'units': units,
            }
            save_state(state, symbol)
            send_telegram(
                f'🚀 *دخول صفقة جديدة — {symbol}*\n\n'
                f'💵 *سعر الدخول:* `${entry_price:,.2f}`\n'
                f'🔴 *وقف الخسارة:* `${entry_price - stop_dist:,.2f}`\n'
                f'🟢 *جني الأرباح:*  `${entry_price + stop_dist * cfg["rr_ratio"]:,.2f}`\n'
                f'📊 *الكمية:* `{units:.5f}` | ⚠️ *المخاطرة:* `${risk_amt:.2f}`'
            )
            logging.info(f'🚀 [{symbol}] فتح صفقة @ ${entry_price:,.2f}')

def create_exchange():
    exchange = ccxt.binance({
        'enableRateLimit': True, 'timeout': 20000,
        'options': {'defaultType': 'spot', 'fetchMarkets': ['spot']},
    })
    exchange.urls['api']['public'] = 'https://data-api.binance.vision/api/v3'
    exchange.urls['api']['v1']     = 'https://data-api.binance.vision/api/v1'
    return exchange

def main():
    prevent_multiple_instances()
    try:
        exchange   = create_exchange()
        start_time = time.time()
        last_hb    = start_time
        logging.info('=' * 60)
        logging.info('🤖 تشغيل محاكي التداول — ' + ' + '.join(SYMBOLS_CONFIG.keys()))
        logging.info('=' * 60)
        while True:
            try:
                for symbol in SYMBOLS_CONFIG:
                    state = load_state(symbol)
                    monitor_live_position(exchange, state, symbol)
                    evaluate_signals_on_candle_close(exchange, state, symbol)
                if time.time() - last_hb >= 6 * 3600:
                    for symbol in SYMBOLS_CONFIG:
                        state = load_state(symbol)
                        send_heartbeat(state, start_time, symbol)
                    last_hb = time.time()
            except (ccxt.RequestTimeout, ccxt.NetworkError) as ne:
                logging.warning(f'⚠️ انقطاع شبكة: {ne}')
            except Exception as e:
                logging.error(f'❌ خطأ: {e}', exc_info=True)
            time.sleep(10)
    finally:
        release_instance_lock()

if __name__ == '__main__':
    main()