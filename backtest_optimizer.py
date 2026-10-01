"""
======================================================================
 🧪 BACKTEST PARAMETER MATRIX OPTIMIZER — محرك تحسين المتغيرات التلقائي
======================================================================
اختبار مئات التوليفات من متغيّرات الاستراتيجية (EMA Fast / Slow / ATR / RR)
لاختيار التوليفة الأكثر ربحية وإحصائية إيجابية على بيانات التاريخ.
"""
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
import itertools
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def fetch_data(symbol='BTC/USDT', timeframe='4h', limit=1000):
    exchange = ccxt.binance({'enableRateLimit': True})
    exchange.urls['api']['public'] = 'https://data-api.binance.vision/api/v3'
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/14, adjust=False).mean()
    
    # Daily Trend Filter
    ohlcv_1d = exchange.fetch_ohlcv(symbol, timeframe='1d', limit=200)
    df_1d = pd.DataFrame(ohlcv_1d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['ema_21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
    df_1d['daily_trend_up'] = df_1d['close'] > df_1d['ema_21']
    df_1d['date'] = df_1d['datetime'].dt.date
    df['prev_date'] = (df['datetime'] - pd.Timedelta(days=1)).dt.date
    df = pd.merge(df, df_1d[['date', 'daily_trend_up']], left_on='prev_date', right_on='date', how='left')
    df['daily_trend_up'] = df['daily_trend_up'].ffill().fillna(False)
    return df

def run_single_backtest(df, fast_ema, slow_ema, atr_mult, rr_ratio, rsi_min=40, risk_pct=0.02, initial_bal=1000.0):
    df_sim = df.copy()
    df_sim['ema_fast'] = df_sim['close'].ewm(span=fast_ema, adjust=False).mean()
    df_sim['ema_slow'] = df_sim['close'].ewm(span=slow_ema, adjust=False).mean()
    
    # RSI
    delta = df_sim['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df_sim['rsi'] = 100 - (100 / (1 + rs))
    
    balance = initial_bal
    trades = []
    position = None
    
    for i in range(35, len(df_sim)):
        c = df_sim.iloc[i]
        prev_c = df_sim.iloc[i-1]
        
        # Check live position
        if position:
            high_price = c['high']
            low_price = c['low']
            
            # Trailing SL update
            if high_price > position['highest_price']:
                position['highest_price'] = high_price
                new_sl = high_price - position['atr_dist']
                if new_sl > position['sl']:
                    position['sl'] = new_sl
            
            if low_price <= position['sl']:
                exit_p = position['sl']
                pnl = (exit_p - position['entry_price']) * position['units']
                balance += pnl
                trades.append(pnl)
                position = None
            elif high_price >= position['tp']:
                exit_p = position['tp']
                pnl = (exit_p - position['entry_price']) * position['units']
                balance += pnl
                trades.append(pnl)
                position = None
        
        # Check new entry
        if position is None:
            cross_up = (prev_c['ema_fast'] <= prev_c['ema_slow']) and (c['ema_fast'] > c['ema_slow'])
            daily_ok = c['daily_trend_up']
            rsi_ok = c['rsi'] >= rsi_min
            
            if cross_up and daily_ok and rsi_ok:
                entry_price = c['close']
                atr_dist = c['atr'] * atr_mult
                stop_dist = atr_dist
                units = (balance * risk_pct) / stop_dist
                position = {
                    'entry_price': entry_price,
                    'highest_price': entry_price,
                    'atr_dist': atr_dist,
                    'sl': entry_price - stop_dist,
                    'tp': entry_price + (stop_dist * rr_ratio),
                    'units': units
                }
    
    if not trades:
        return {'profit_factor': 0, 'win_rate': 0, 'total_trades': 0, 'return_pct': 0}
    
    pnls = np.array(trades)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    win_rate = (len(wins) / len(trades)) * 100
    gross_p = wins.sum() if len(wins) > 0 else 0
    gross_l = abs(losses.sum()) if len(losses) > 0 else 0
    pf = (gross_p / gross_l) if gross_l > 0 else 999.0
    ret_pct = ((balance - initial_bal) / initial_bal) * 100
    
    return {
        'profit_factor': pf,
        'win_rate': win_rate,
        'total_trades': len(trades),
        'return_pct': ret_pct,
        'final_balance': balance
    }

def main():
    symbol = 'BTC/USDT'
    print(f"📥 جلب البيانات التاريخية لـ {symbol}...")
    df = fetch_data(symbol=symbol, timeframe='4h', limit=1000)
    print(f"✅ تم جلب {len(df)} شمعة 4H. بدء مصفوفة تحسين المتغيرات (Grid Search)...\n")
    
    fast_emas = [5, 8, 10, 12]
    slow_emas = [20, 30, 40, 50]
    atr_mults = [1.5, 2.0, 2.5]
    rr_ratios = [2.0, 2.5, 3.0]
    
    results = []
    
    for f, s, a, r in itertools.product(fast_emas, slow_emas, atr_mults, rr_ratios):
        if f >= s: continue
        res = run_single_backtest(df, fast_ema=f, slow_ema=s, atr_mult=a, rr_ratio=r)
        if res['total_trades'] >= 10:
            results.append({
                'Fast': f, 'Slow': s, 'ATR_Mult': a, 'RR': r,
                'PF': res['profit_factor'], 'WinRate': res['win_rate'],
                'Trades': res['total_trades'], 'ReturnPct': res['return_pct']
            })
    
    df_res = pd.DataFrame(results).sort_values(by='PF', ascending=False)
    
    print("=" * 85)
    print(" 🏆 أفضل 10 توليفات استراتيجية إحصائياً (مرتبة حسب معامل الربحية Profit Factor)")
    print("=" * 85)
    print(df_res.head(10).to_string(index=False))
    print("=" * 85)

if __name__ == '__main__':
    main()