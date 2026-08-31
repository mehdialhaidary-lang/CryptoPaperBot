import numpy as np
import pandas as pd

def run_monte_carlo(trade_returns, initial_balance=100.0, num_simulations=10000):
    """
    محاكاة مونتي كارلو بإعادة سحب عينات الصفقات (Bootstrap Resampling)
    لتقييم المخاطر والتراجع الأقصى وتوزيع العوائد المتوقعة.
    """
    num_trades = len(trade_returns)
    returns_arr = np.array(trade_returns)

    final_returns = []
    max_drawdowns = []
    max_consecutive_losses = []

    np.random.seed(42)

    for _ in range(num_simulations):
        # سحب عشوائي مع الإعادة (Resampling with Replacement)
        sim_returns = np.random.choice(returns_arr, size=num_trades, replace=True)

        curr_bal = initial_balance
        equity_curve = [initial_balance]
        consec_loss = 0
        max_consec = 0

        for ret in sim_returns:
            curr_bal *= (1 + ret)
            equity_curve.append(curr_bal)

            if ret < 0:
                consec_loss += 1
                if consec_loss > max_consec:
                    max_consec = consec_loss
            else:
                consec_loss = 0

        eq_arr = np.array(equity_curve)
        peak = np.maximum.accumulate(eq_arr)
        drawdown = (peak - eq_arr) / peak
        max_dd = np.max(drawdown)

        ret_pct = ((curr_bal - initial_balance) / initial_balance) * 100
        final_returns.append(ret_pct)
        max_drawdowns.append(max_dd * 100)
        max_consecutive_losses.append(max_consec)

    return {
        'returns': np.array(final_returns),
        'drawdowns': np.array(max_drawdowns),
        'consecutive_losses': np.array(max_consecutive_losses)
    }

if __name__ == "__main__":
    # عوائد صفقات استراتيجية EMA Cross الفعلية (نفس استراتيجية paper_trading.py و backtest_ema_strategy.py)
    from backtest_ema_strategy import fetch_historical_data, run_backtest, CONFIG as BT_CONFIG

    print("📥 جلب البيانات التاريخية وتشغيل باك-تست EMA Cross لاستخراج الصفقات...")
    df = fetch_historical_data()
    _, trades = run_backtest(df)
    trade_returns = [t['pnl_pct'] for t in trades]

    if not trade_returns:
        raise SystemExit("❌ لم يتم العثور على أي صفقات من باك-تست EMA Cross — لا يمكن تشغيل المحاكاة.")

    print(f"✅ تم استخراج {len(trade_returns)} صفقة فعلية من استراتيجية EMA Cross (الفترة الكاملة {df['datetime'].iloc[0].strftime('%Y-%m-%d')} → {df['datetime'].iloc[-1].strftime('%Y-%m-%d')})\n")

    print("🎲 جاري تشغيل محاكاة مونتي كارلو (10,000 جولة)...\n")
    results = run_monte_carlo(trade_returns, initial_balance=BT_CONFIG['initial_balance'], num_simulations=10000)

    returns = results['returns']
    dds = results['drawdowns']
    consec = results['consecutive_losses']

    print("=" * 70)
    print(" 🎯 نتائج محاكاة مونتي كارلو للاستراتيجية (10,000 جولة محاكاة)")
    print("=" * 70)
    print(f"إجمالي عدد الصفقات المحاكاة في كل جولة: {len(trade_returns)} صفقة")
    print("-" * 70)
    print("📊 توزيع العائد النهائي (Total Return %):")
    print(f"  • سيناريو الحظ السيء (5th Percentile):   {np.percentile(returns, 5):+.2f}%")
    print(f"  • العائد الوسيط المتوقع (Median 50th):   {np.median(returns):+.2f}%")
    print(f"  • سيناريو الحظ الممتد (95th Percentile):  {np.percentile(returns, 95):+.2f}%")
    print(f"  • نسبة احتمالية إنهاء التداول بربح:      {(returns > 0).mean() * 100:.1f}%")
    print("-" * 70)
    print("🔻 توزيع أقصى تراجع محتمل (Max Drawdown %):")
    print(f"  • التراجع المتوقع (Median Max DD):      {np.median(dds):.2f}%")
    print(f"  • التراجع في أسوأ 5% من الحالات (95th):   {np.percentile(dds, 95):.2f}%")
    print(f"  • أقصى تراجع مطلق سجلته المحاكاة:        {np.max(dds):.2f}%")
    print("-" * 70)
    print("⚠️ احتمالات تقييم المخاطر (Risk Probabilities):")
    print(f"  • احتمال كسر تراجع 15%:                 {(dds > 15).mean() * 100:.1f}%")
    print(f"  • احتمال كسر تراجع 20%:                 {(dds > 20).mean() * 100:.1f}%")
    print(f"  • احتمال كسر تراجع 25%:                 {(dds > 25).mean() * 100:.1f}%")
    print("-" * 70)
    print("📉 الخسائر المتتالية (Consecutive Losses):")
    print(f"  • المتوسط المتوقع لأطول سلسلة خسائر:    {np.median(consec):.0f} صفقات متتالية")
    print(f"  • أقصى سلسلة خسائر متتالية متوقعة (95%):  {np.percentile(consec, 95):.0f} صفقات متتالية")
    print("=" * 70)