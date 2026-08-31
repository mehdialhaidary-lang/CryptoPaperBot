import json
import os
import time
from datetime import datetime

STATE_FILE = 'paper_state.json'
REFRESH_INTERVAL = 10  # التحديث كل 10 ثوانٍ

def load_data():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def display_dashboard():
    # مسح الشاشة لتحديث العرض
    os.system('cls' if os.name == 'nt' else 'clear')

    data = load_data()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if not data:
        print(f"[{now_str}] ⚠️ لم يتم العثور على ملف البيانات '{STATE_FILE}'. بانتظار تشغيل البوت...")
        return

    balance = data.get('balance', 0.0)
    initial_balance = data.get('initial_balance', 1000.0)
    position = data.get('position')
    history = data.get('trades', [])

    total_return_pct = ((balance - initial_balance) / initial_balance) * 100 if initial_balance else 0.0

    total_trades = len(history)
    wins = [t for t in history if t.get('pnl', 0) > 0]
    losses = [t for t in history if t.get('pnl', 0) <= 0]

    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0.0

    gross_profit = sum(t.get('pnl', 0) for t in wins)
    gross_loss = abs(sum(t.get('pnl', 0) for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

    print("=" * 65)
    print(f" 📊 لوحة متابعة التداول الافتراضي (Live Dashboard) | {now_str}")
    print("=" * 65)
    print(f" 💰 الرصيد الحالي:        ${balance:,.2f}")
    print(f" 📈 إجمالي العائد:         {total_return_pct:+.2f}% (${balance - initial_balance:+.2f})")
    print(f" 🔄 إجمالي الصفقات المغلقة: {total_trades}")
    print(f" 🎯 نسبة النجاح (Win Rate): {win_rate:.1f}% ({len(wins)} رابحة / {len(losses)} خاسرة)")
    print(f" ⚖️ مائل الربحية (Profit Factor): {profit_factor:.2f}")
    print("-" * 65)

    print(" 📍 الصفقة المفتوحة الحالية:")
    if position:
        print(f"   • وقت الدخول:       {position.get('entry_time', '-')}")
        print(f"   • سعر الدخول:       ${position.get('entry_price', 0):,.2f}")
        print(f"   • وقف الخسارة (SL):  ${position.get('sl', 0):,.2f}")
        print(f"   • جني الأرباح (TP):  ${position.get('tp', 0):,.2f}")
        print(f"   • حجم المركز:        {position.get('units', 0):.4f} BTC")
    else:
        print("   • لا توجد صفقة مفتوحة حالياً (البوت في حالة انتظار لإشارة دخول).")

    print("-" * 65)
    print(" 📜 أحدث 5 صفقات مغلقة:")
    if history:
        for i, t in enumerate(reversed(history[-5:]), 1):
            print(f"   {i}. [{str(t.get('exit_time', ''))[:16]}] {t.get('reason', '')}")
            print(f"      الدخول: ${t.get('entry_price', 0):,.2f} | الخروج: ${t.get('exit_price', 0):,.2f}")
            print(f"      الربح/الخسارة: ${t.get('pnl', 0):+.2f} | الرصيد: ${t.get('balance_after', 0):,.2f}")
    else:
        print("   • لا يوجد سجل صفقات مغلقة حتى الآن.")
    print("=" * 65)
    print(f"⏱️ التحديث تلقائي كل {REFRESH_INTERVAL} ثوانٍ... (إيقاف: Ctrl+C)")

if __name__ == "__main__":
    try:
        while True:
            display_dashboard()
            time.sleep(REFRESH_INTERVAL)
    except KeyboardInterrupt:
        print("\n👋 تم إيقاف شاشة المتابعة.")
