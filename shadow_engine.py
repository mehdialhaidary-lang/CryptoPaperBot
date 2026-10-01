"""
======================================================================
 👤 SHADOW QDS ENGINE — محرك القرار المطور في وضع الظل (Sidecar Runner)
======================================================================
يعمل بالتوازي مع المحرك الحالي (Legacy Engine) دون المساس به إطلاقاً.
يقرأ البيانات، يتخذ قرار الـ QDS، ويسجل الفروق والفرص الضائعة إحصائياً.
"""
import os
import json
import logging
import time
from datetime import datetime, timezone
import pandas as pd

import data_validator
import market_regime
import risk_manager
import gemini_validator
import trade_memory

SHADOW_STATE_FILE = "shadow_state.json"

def load_shadow_state() -> dict:
    if os.path.exists(SHADOW_STATE_FILE):
        try:
            with open(SHADOW_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"hypothetical_positions": {}, "shadow_balance": 5000.0, "initial_balance": 5000.0, "trades": []}

def save_shadow_state(state: dict):
    tmp = SHADOW_STATE_FILE + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4, default=str, ensure_ascii=False)
    os.replace(tmp, SHADOW_STATE_FILE)

def evaluate_shadow_qds_cycle(symbol: str, df_4h: pd.DataFrame, df_1d: pd.DataFrame, legacy_decision: str, current_price: float, symbol_states: dict) -> dict:
    """
    تقييم شمعة مغلقة عبر نظام الـ QDS في وضع الظل (Shadow Mode).
    """
    # 1. Data Quality Check
    is_valid, q_score, q_reason = data_validator.validate_ohlcv_dataframe(df_4h, expected_timeframe_hours=4)
    data_quality = {"score": q_score, "status": q_reason if is_valid else "INVALID"}

    if not is_valid:
        qds_decision = "WAIT"
        reason = f"إلغاء QDS: فحص جودة البيانات فشل ({q_reason})"
        return {"decision": qds_decision, "reason": reason}

    # 2. Market Regime Analysis
    regime_info = market_regime.detect_market_regime(df_4h, df_1d)
    
    # 3. Technical Score (0 - 100)
    closed_candle = df_4h.iloc[-2]
    prev_closed = df_4h.iloc[-3]
    cross_up = (prev_closed['ema_fast'] <= prev_closed['ema_slow']) and (closed_candle['ema_fast'] > closed_candle['ema_slow'])
    daily_up = bool(closed_candle.get('daily_trend_up', False))
    rsi_val = float(closed_candle.get('rsi', 50.0))
    rsi_ok = rsi_val >= 40

    tech_score = 0.0
    if cross_up: tech_score += 40.0
    if daily_up: tech_score += 30.0
    if rsi_ok:   tech_score += 30.0

    # 4. Gemini Analyst Validation (لو متوفر)
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    gemini_data = {
        "status": "NOT_CONFIGURED" if not gemini_key else "SKIPPED",
        "sentiment_score": 0.0,
        "impact": "LOW",
        "confidence": 0.0,
        "safe": True,
        "reason": "لم يتم تفعيل الذكاء الاصطناعي"
    }

    # 5. Portfolio Risk Manager
    account_bal = symbol_states.get(symbol, {}).get('balance', 1000.0)
    atr_val = float(closed_candle.get('atr', current_price * 0.01))
    stop_dist = atr_val * 2.0
    stop_price = current_price - stop_dist

    risk_eval = risk_manager.evaluate_portfolio_risk(
        symbol=symbol,
        account_balance=account_bal,
        entry_price=current_price,
        stop_price=stop_price,
        all_symbol_states=symbol_states
    )

    # 6. QDS Decision Logic
    qds_decision = "WAIT"
    wait_reasons = []
    
    if not cross_up:
        wait_reasons.append("لا يوجد تقاطع EMA صاعد طازج")
    if not daily_up:
        wait_reasons.append("الاتجاه اليومي هابط")
    if not rsi_ok:
        wait_reasons.append(f"RSI ({rsi_val:.1f}) أقل من 40")
    if not risk_eval["allowed"]:
        wait_reasons.append(f"مخاطرة المحفظة: {risk_eval['reason']}")
    if not gemini_data["safe"]:
        wait_reasons.append(f"حماية Gemini: {gemini_data['reason']}")

    if cross_up and daily_up and rsi_ok and risk_eval["allowed"] and gemini_data["safe"]:
        qds_decision = "BUY"
        decision_reason = f"QDS BUY: جميع الشروط مكتملة (Regime: {regime_info['regime']} | Score: {tech_score:.0f})"
        wait_reason_str = ""
    else:
        qds_decision = "WAIT"
        wait_reason_str = " · ".join(wait_reasons)
        decision_reason = f"QDS WAIT: {wait_reason_str} (Regime: {regime_info['regime']})"

    # 7. التسجيل في ذاكرة الصفقات (Trade Memory)
    trade_id = f"shadow_{symbol.replace('/','_')}_{int(closed_candle['timestamp'])}"
    rec = trade_memory.build_trade_record(
        trade_id=trade_id,
        symbol=symbol,
        legacy_decision=legacy_decision,
        qds_decision=qds_decision,
        market_regime=regime_info,
        technical_score=tech_score,
        gemini_data=gemini_data,
        risk_data=risk_eval,
        data_quality=data_quality,
        decision_reason=decision_reason,
        wait_reason=wait_reason_str,
        entry_price=current_price if legacy_decision == "BUY" else 0.0,
        hypothetical_entry=current_price if qds_decision == "BUY" else 0.0
    )
    trade_memory.record_decision_event(rec)

    logging.info(f"👤 [Shadow QDS] {symbol} | Legacy: {legacy_decision} | QDS: {qds_decision} | {decision_reason}")

    return {
        "decision": qds_decision,
        "reason": decision_reason,
        "wait_reason": wait_reason_str,
        "regime": regime_info["regime"],
        "tech_score": tech_score,
        "risk_eval": risk_eval
    }