"""
نسخة تشغيل واحدة (Single-Run) — مخصصة للتشغيل عبر GitHub Actions.
كل تشغيلة: تحمّل الحالة لكل زوج -> تفحص -> تحفظ -> تخرج.
"""
import time
import logging
import ccxt

from paper_trading import (
    SYMBOLS_CONFIG,
    load_state,
    save_state,
    monitor_live_position,
    evaluate_signals_on_candle_close,
    send_telegram,
    send_heartbeat,
    create_exchange,
)


def send_heartbeat_if_due(exchange):
    """إرسال نبضة حياة لكل زوج إذا حان وقتها."""
    start_time = time.time()
    for symbol in SYMBOLS_CONFIG:
        try:
            state = load_state(symbol)
            interval_sec = SYMBOLS_CONFIG[symbol]['heartbeat_interval_hours'] * 3600
            last_hb      = state.get('last_heartbeat_time', 0)
            if time.time() - last_hb >= interval_sec:
                send_heartbeat(state, start_time, symbol)
                state['last_heartbeat_time'] = time.time()
                save_state(state, symbol)
        except Exception as e:
            logging.error(f"[{symbol}] خطأ في نبضة الحياة: {e}")


def run_shadow_sidecar(exchange, symbol: str):
    """تشغيل تقييم نظام الـ QDS في وضع الظل (Shadow Mode) دون التأثير على التداول الفعلي."""
    try:
        from paper_trading import fetch_strict_data
        df_4h = fetch_strict_data(exchange, symbol)
        if df_4h is not None and len(df_4h) >= 50:
            ticker = exchange.fetch_ticker(symbol)
            cur_price = ticker['last']
            all_states = {s: load_state(s) for s in SYMBOLS_CONFIG}
            leg_state = all_states.get(symbol, {})
            leg_pos = leg_state.get('position')
            legacy_dec = "BUY" if leg_pos is not None else "WAIT"
            
            import shadow_engine
            shadow_engine.evaluate_shadow_qds_cycle(
                symbol=symbol,
                df_4h=df_4h,
                df_1d=None,
                legacy_decision=legacy_dec,
                current_price=cur_price,
                symbol_states=all_states
            )
    except Exception as e:
        logging.warning(f"[{symbol}] ⚠️ Sidecar QDS Evaluation skipped: {e}")


def run_symbol(exchange, symbol: str):
    """تشغيل دورة كاملة لزوج واحد."""
    try:
        state = load_state(symbol)
        monitor_live_position(exchange, state, symbol)
        evaluate_signals_on_candle_close(exchange, state, symbol)
        
        # 👤 تشغيل محرك الظل QDS بالتوازي (Sidecar Shadow Evaluation)
        run_shadow_sidecar(exchange, symbol)
        
        logging.info(f"[{symbol}] ✅ الدورة مكتملة.")
    except (ccxt.RequestTimeout, ccxt.NetworkError) as ne:
        logging.warning(f"[{symbol}] ⚠️ انقطاع شبكة مؤقت: {ne}")
        send_telegram(
            f"⚠️ *فشل فحص {symbol} (انقطاع شبكة)*\n"
            f"`{ne}`\n"
            f"سيُعاد المحاولة في الدورة القادمة (~15 دقيقة)."
        )
    except Exception as e:
        logging.error(f"[{symbol}] ❌ خطأ غير متوقع: {e}", exc_info=True)
        send_telegram(
            f"🚨 *خطأ غير متوقع في البوت — {symbol}*\n\n"
            f"`{type(e).__name__}: {e}`\n\n"
            f"راجع سجل GitHub Actions للتفاصيل."
        )


def main():
    exchange = create_exchange()

    logging.info("=" * 60)
    logging.info("🤖 GitHub Actions — بدء الدورة لكل الأزواج")
    logging.info("=" * 60)

    for symbol in SYMBOLS_CONFIG:
        logging.info(f"🔍 فحص {symbol}...")
        run_symbol(exchange, symbol)

    send_heartbeat_if_due(exchange)

    logging.info("✅ انتهت جميع الدورات.")


if __name__ == "__main__":
    main()