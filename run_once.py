"""
نسخة تشغيل واحدة (Single-Run) من البوت، مخصصة للتشغيل عبر GitHub Actions
كل تشغيلة: تحمّل الحالة -> تفحص السعر/الشمعة مرة واحدة -> تحفظ الحالة -> تخرج.
لا تحتوي على حلقة لا نهائية ولا قفل عملية (كل تشغيلة معزولة، والجدولة تمنع التداخل).
"""
import time
import logging
import ccxt

from paper_trading import (
    CONFIG,
    load_state,
    save_state,
    monitor_live_position,
    evaluate_signals_on_candle_close,
    send_telegram,
    create_exchange,
)


def send_heartbeat_if_due(state):
    interval_sec = CONFIG['heartbeat_interval_hours'] * 3600
    last_heartbeat = state.get('last_heartbeat_time', 0)

    if time.time() - last_heartbeat < interval_sec:
        return

    pos_status = "لا توجد صفقة مفتوحة" if state['position'] is None else \
        f"صفقة مفتوحة @ ${state['position']['entry_price']:,.2f}"

    msg = (
        f"💓 *نبضة حياة (GitHub Actions)*\n\n"
        f"✅ البوت يعمل بشكل طبيعي (تشغيل مجدوَل)\n"
        f"💰 الرصيد الحالي: `${state['balance']:,.2f}`\n"
        f"📍 الحالة: {pos_status}\n"
        f"🔄 عدد الصفقات المغلقة: {len(state['trades'])}"
    )
    send_telegram(msg)
    logging.info("💓 تم إرسال نبضة حياة (GitHub Actions)")

    state['last_heartbeat_time'] = time.time()
    save_state(state)


def main():
    state = load_state()
    exchange = create_exchange()

    try:
        monitor_live_position(exchange, state)
        evaluate_signals_on_candle_close(exchange, state)
    except (ccxt.RequestTimeout, ccxt.NetworkError) as ne:
        logging.warning(f"⚠️ انقطاع مؤقت في الشبكة/المنصة: {ne}")
        send_telegram(
            f"⚠️ *تنبيه: فشل فحص السوق (انقطاع شبكة مؤقت)*\n\n"
            f"`{ne}`\n\n"
            f"سيُعاد المحاولة تلقائيًا في الدورة القادمة (~15 دقيقة)."
        )
    except Exception as e:
        logging.error(f"❌ خطأ غير متوقع أثناء الدورة: {e}", exc_info=True)
        send_telegram(
            f"🚨 *تنبيه: خطأ غير متوقع في البوت*\n\n"
            f"`{type(e).__name__}: {e}`\n\n"
            f"راجع سجل GitHub Actions للتفاصيل الكاملة."
        )

    send_heartbeat_if_due(state)


if __name__ == "__main__":
    main()
