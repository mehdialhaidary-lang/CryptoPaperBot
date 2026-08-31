import ccxt
import pandas as pd
import numpy as np
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =========================================================
# ⚙️ إعدادات اختبار استراتيجية EMA Cross (نفس إعدادات paper_trading.py)
# =========================================================
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
    'commission_pct': 0.001,     # 0.1% عمولة منصة
    'slippage_pct': 0.0005,      # 0.05% انزلاق سعري
    'spread_pct': 0.0002,        # 0.02% فارق العرض والطلب
    'initial_balance': 1000.0,
    'split_ratio': 0.70,
    'start_date': '2023-01-01T00:00:00Z'
}

def fetch_historical_data():
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'timeout': 20000,
        'options': {'defaultType': 'spot', 'fetchMarkets': ['spot']}
    })

    print("📥 جلب البيانات التاريخية (4H + يومي)...")

    # بيانات 4H
    ohlcv_4h = []
    since = exchange.parse8601(CONFIG['start_date'])
    while True:
        data = exchange.fetch_ohlcv(CONFIG['symbol'], timeframe='4h', since=since, limit=1000)
        if not data:
            break
        ohlcv_4h.extend(data)
        since = data[-1][0] + 1
        if len(data) < 1000:
            break

    # بيانات يومية
    ohlcv_1d = []
    since_1d = exchange.parse8601(CONFIG['start_date'])
    while True:
        data = exchange.fetch_ohlcv(CONFIG['symbol'], timeframe='1d', since=since_1d, limit=1000)
        if not data:
            break
        ohlcv_1d.extend(data)
        since_1d = data[-1][0] + 1
        if len(data) < 1000:
            break

    df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df_1d = pd.DataFrame(ohlcv_1d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms', utc=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms', utc=True)

    # الاتجاه اليومي عبر EMA 21 (شمعة اليوم السابق لمنع التسريب)
    df_1d['ema_21_1d'] = df_1d['close'].ewm(span=21, adjust=False).mean()
    df_1d['daily_trend_up'] = df_1d['close'] > df_1d['ema_21_1d']
    df_1d['daily_date'] = df_1d['datetime'].dt.date

    df_4h['prev_daily_date'] = (df_4h['datetime'] - pd.Timedelta(days=1)).dt.date

    df = pd.merge(
        df_4h,
        df_1d[['daily_date', 'daily_trend_up']],
        left_on='prev_daily_date',
        right_on='daily_date',
        how='left'
    )
    df['daily_trend_up'] = df['daily_trend_up'].ffill().fillna(False).astype(bool)

    # مؤشرات 4H (مطابقة تماماً لحسابات paper_trading.py)
    df['ema_fast'] = df['close'].ewm(span=CONFIG['fast_ema'], adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=CONFIG['slow_ema'], adjust=False).mean()

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/CONFIG['rsi_period'], adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/CONFIG['rsi_period'], adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))

    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/CONFIG['atr_period'], adjust=False).mean()

    return df.dropna(subset=['atr', 'rsi']).reset_index(drop=True)

def check_exit(pos, candle):
    """فحص ضرب SL/TP داخل الشمعة (الوقف أولاً افتراضاً للتحفظ)"""
    if candle['open'] <= pos['sl']:
        return candle['open'], 'GAP_STOP_LOSS'
    if candle['low'] <= pos['sl']:
        return pos['sl'], 'STOP_LOSS'
    if candle['open'] >= pos['tp']:
        return candle['open'], 'GAP_TAKE_PROFIT'
    if candle['high'] >= pos['tp']:
        return pos['tp'], 'TAKE_PROFIT'
    return None, None

def close_trade(pos, exit_price, reason, exit_time, balance, trades):
    effective_exit = exit_price * (1 - CONFIG['slippage_pct'] - CONFIG['spread_pct'])
    gross_pnl = (effective_exit - pos['entry_price']) * pos['units']
    fees = (pos['entry_price'] * pos['units'] * CONFIG['commission_pct']) + (effective_exit * pos['units'] * CONFIG['commission_pct'])
    net_pnl = gross_pnl - fees
    pnl_pct = net_pnl / balance
    balance += net_pnl
    trades.append({
        'entry_time': pos['entry_time'],
        'exit_time': exit_time,
        'pnl': net_pnl,
        'pnl_pct': pnl_pct,
        'reason': reason,
        'balance': balance
    })
    return balance

def run_backtest(df):
    balance = CONFIG['initial_balance']
    position = None
    trades = []

    for i in range(1, len(df)):
        current = df.iloc[i]
        signal = df.iloc[i-1]

        # 1. إدارة الصفقة المفتوحة (SL/TP داخل الشمعة ثم الإشارة العكسية عند الافتتاح)
        if position is not None:
            exit_price, reason = check_exit(position, current)
            if exit_price is None:
                cross_down = (signal['ema_fast'] >= signal['ema_slow']) and (current['ema_fast'] < current['ema_slow'])
                if cross_down:
                    exit_price, reason = current['open'], 'REVERSE_SIGNAL'
            if exit_price is not None:
                balance = close_trade(position, exit_price, reason, current['datetime'], balance, trades)
                position = None

        # 2. دخول جديد عند تقاطع صاعد + اتجاه يومي + RSI (إشارة الشمعة المغلقة، تنفيذ عند افتتاح الحالية)
        if position is None:
            cross_up = (signal['ema_fast'] <= signal['ema_slow']) and (current['ema_fast'] > current['ema_slow'])
            daily_ok = bool(signal['daily_trend_up'])
            rsi_ok = signal['rsi'] >= 40

            if cross_up and daily_ok and rsi_ok:
                raw_entry = current['open']
                entry_price = raw_entry * (1 + CONFIG['slippage_pct'] + CONFIG['spread_pct'])

                stop_dist = signal['atr'] * CONFIG['atr_mult']
                if stop_dist > 0:
                    risk_amt = balance * CONFIG['risk_pct']
                    units = min(risk_amt / stop_dist, balance / entry_price)

                    position = {
                        'entry_time': current['datetime'],
                        'entry_price': entry_price,
                        'sl': entry_price - stop_dist,
                        'tp': entry_price + stop_dist * CONFIG['rr_ratio'],
                        'units': units
                    }

                    # فحص SL/TP داخل نفس شمعة الدخول (البوت المباشر يراقب لحظياً)
                    exit_price, reason = check_exit(position, current)
                    if exit_price is not None:
                        balance = close_trade(position, exit_price, reason, current['datetime'], balance, trades)
                        position = None

    return calculate_metrics(trades, balance), trades

def calculate_metrics(trades, final_balance):
    if not trades:
        return {'total_trades': 0, 'final_balance': final_balance, 'return_pct': 0, 'win_rate': 0, 'profit_factor': 0, 'max_drawdown': 0, 'expectancy': 0}

    df_t = pd.DataFrame(trades)
    pnls = df_t['pnl'].values
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    return_pct = ((final_balance - CONFIG['initial_balance']) / CONFIG['initial_balance']) * 100
    win_rate = (len(wins) / len(trades)) * 100
    gross_profit = wins.sum() if len(wins) > 0 else 0
    gross_loss = abs(losses.sum()) if len(losses) > 0 else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else np.inf
    expectancy = pnls.mean()

    balances = [CONFIG['initial_balance']] + df_t['balance'].tolist()
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
        'final_balance': final_balance,
        'return_pct': return_pct,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_drawdown': max_dd * 100,
        'expectancy': expectancy
    }

def main():
    df = fetch_historical_data()
    split_idx = int(len(df) * CONFIG['split_ratio'])

    df_is = df.iloc[:split_idx].reset_index(drop=True)
    df_oos = df.iloc[split_idx:].reset_index(drop=True)

    print(f"\n📊 الفترة الإجمالية للبيانات: من {df['datetime'].iloc[0].strftime('%Y-%m-%d')} إلى {df['datetime'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"🔹 In-Sample (IS):    {len(df_is)} شمعة ({df_is['datetime'].iloc[0].strftime('%Y-%m-%d')} -> {df_is['datetime'].iloc[-1].strftime('%Y-%m-%d')})")
    print(f"🔸 Out-of-Sample (OOS): {len(df_oos)} شمعة ({df_oos['datetime'].iloc[0].strftime('%Y-%m-%d')} -> {df_oos['datetime'].iloc[-1].strftime('%Y-%m-%d')})")

    res_is, trades_is = run_backtest(df_is)
    res_oos, trades_oos = run_backtest(df_oos)

    print("\n" + "="*70)
    print(" 🎯 نتائج اختبار استراتيجية (EMA Cross + RSI + Daily Trend - 4H)")
    print("="*70)
    print(f"{'المعيار (Metric)':<25} | {'In-Sample (70%)':<20} | {'Out-of-Sample (30%)':<20}")
    print("-" * 70)
    print(f"{'إجمالي الصفقات':<25} | {res_is['total_trades']:<20} | {res_oos['total_trades']:<20}")
    print(f"{'العائد النهائي (%)':<25} | {res_is['return_pct']:+.2f}%{'':<14} | {res_oos['return_pct']:+.2f}%")
    print(f"{'نسبة النجاح (Win Rate)':<25} | {res_is['win_rate']:.1f}%{'':<15} | {res_oos['win_rate']:.1f}%")
    print(f"{'مائل الربحية (Profit Factor)':<25} | {res_is['profit_factor']:.2f}{'':<16} | {res_oos['profit_factor']:.2f}")
    print(f"{'أقصى تراجع (Max Drawdown)':<25} | {res_is['max_drawdown']:.2f}%{'':<14} | {res_oos['max_drawdown']:.2f}%")
    print(f"{'معدل ربح الصفقة (Expectancy)':<25} | ${res_is['expectancy']:+.2f}{'':<14} | ${res_oos['expectancy']:+.2f}")
    print("="*70)

if __name__ == "__main__":
    main()
