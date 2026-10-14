"""
======================================================================
 📊 MARKET REGIME ENGINE — محرك حالة السوق (Configurable Parameterized)
======================================================================
يقوم بتصنيف حالة السوق إلى:
- TRENDING_UP
- TRENDING_DOWN
- SIDEWAYS
- HIGH_VOLATILITY
- LOW_VOLATILITY
بدون أي افتراضات مجحفة، ومع إمكانية تعديل جميع العتبات (Thresholds).
"""
import pandas as pd
import numpy as np
import json
import os

DEFAULT_REGIME_CONFIG = {
    "adx_period": 14,
    "adx_trending_threshold": 22.0,
    "adx_sideways_threshold": 18.0,
    "atr_ratio_high_vol": 1.4,
    "atr_ratio_low_vol": 0.7,
    "bb_period": 20,
    "bb_std": 2.0,
    "bb_width_squeeze": 0.03
}

def calculate_dmi(df: pd.DataFrame, period: int = 14) -> tuple:
    """حساب مؤشرات ADX, +DI, -DI لتحديد قوة واتجاه السوق كمياً."""
    df_c = df.copy()
    df_c['up'] = df_c['high'] - df_c['high'].shift(1)
    df_c['down'] = df_c['low'].shift(1) - df_c['low']
    
    df_c['plus_dm'] = np.where((df_c['up'] > df_c['down']) & (df_c['up'] > 0), df_c['up'], 0.0)
    df_c['minus_dm'] = np.where((df_c['down'] > df_c['up']) & (df_c['down'] > 0), df_c['down'], 0.0)
    
    high_low = df_c['high'] - df_c['low']
    high_close = (df_c['high'] - df_c['close'].shift(1)).abs()
    low_close = (df_c['low'] - df_c['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (pd.Series(df_c['plus_dm']).ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (pd.Series(df_c['minus_dm']).ewm(alpha=1/period, adjust=False).mean() / atr)
    
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx.fillna(0.0), plus_di.fillna(0.0), minus_di.fillna(0.0)

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """حساب مؤشر ADX لتحديد قوة الاتجاه (متوافق خلفياً)."""
    return calculate_dmi(df, period)[0]

def detect_market_regime(df_4h: pd.DataFrame, df_1d: pd.DataFrame = None, config: dict = None) -> dict:
    """
    تحليل وتصنيف حالة السوق الحالية إحصائياً.
    إرجاع dict يشمل نوع الـ Regime والمؤشرات التفصيلية.
    """
    cfg = config or DEFAULT_REGIME_CONFIG
    if df_4h is None or len(df_4h) < 35:
        return {
            "regime": "UNKNOWN",
            "adx": 0.0,
            "atr_ratio": 1.0,
            "bb_width": 0.0,
            "is_trending": False,
            "details": "بيانات غير كافية"
        }

    c = df_4h.iloc[-2]  # الشمعة المغلقة الأخيرة
    
    # 1. ADX and DMI (+DI / -DI)
    adx_series, plus_di_series, minus_di_series = calculate_dmi(df_4h, period=cfg.get("adx_period", 14))
    current_adx = float(adx_series.iloc[-2])
    current_plus_di = float(plus_di_series.iloc[-2])
    current_minus_di = float(minus_di_series.iloc[-2])
    
    # 2. ATR Ratio (مقارنة الـ ATR الحالي بمتوسط الـ ATR لـ 20 شمعة)
    atr_curr = float(c.get('atr', 0.0))
    atr_ma = float(df_4h['atr'].tail(20).mean()) if 'atr' in df_4h.columns else atr_curr
    atr_ratio = (atr_curr / atr_ma) if atr_ma > 0 else 1.0
    
    # 3. Bollinger Bands Width
    bb_period = cfg.get("bb_period", 20)
    sma = df_4h['close'].rolling(window=bb_period).mean()
    std = df_4h['close'].rolling(window=bb_period).std()
    upper_bb = sma + (std * cfg.get("bb_std", 2.0))
    lower_bb = sma - (std * cfg.get("bb_std", 2.0))
    bb_width = float(((upper_bb.iloc[-2] - lower_bb.iloc[-2]) / sma.iloc[-2])) if sma.iloc[-2] > 0 else 0.0

    # 4. تصنيف حالة السوق
    regime = "SIDEWAYS"
    if current_adx >= cfg.get("adx_trending_threshold", 22.0):
        if 'ema_fast' in c and 'ema_slow' in c and pd.notna(c.get('ema_fast')) and pd.notna(c.get('ema_slow')):
            regime = "TRENDING_UP" if c['ema_fast'] > c['ema_slow'] else "TRENDING_DOWN"
        else:
            regime = "TRENDING_UP" if current_plus_di >= current_minus_di else "TRENDING_DOWN"
    elif current_adx <= cfg.get("adx_sideways_threshold", 18.0) or bb_width <= cfg.get("bb_width_squeeze", 0.03):
        regime = "SIDEWAYS"
    elif atr_ratio >= cfg.get("atr_ratio_high_vol", 1.4):
        regime = "HIGH_VOLATILITY"
    elif atr_ratio <= cfg.get("atr_ratio_low_vol", 0.7):
        regime = "LOW_VOLATILITY"

    return {
        "regime": regime,
        "adx": round(current_adx, 2),
        "plus_di": round(current_plus_di, 2),
        "minus_di": round(current_minus_di, 2),
        "atr_ratio": round(atr_ratio, 2),
        "bb_width": round(bb_width, 4),
        "is_trending": "TRENDING" in regime,
        "details": f"ADX: {current_adx:.1f} (+DI: {current_plus_di:.1f} | -DI: {current_minus_di:.1f}) | ATR Ratio: {atr_ratio:.2f} | BB Width: {bb_width:.3f}"
    }

def calculate_qds_composite_score(regime_info: dict, technical_indicators: dict, risk_eval: dict) -> dict:
    """
    حساب الدرجة المركبة لإشارة QDS (0 إلى 100) وفلاتر حماية المحفظة المعتمدة من مجلس الذكاء الاصطناعي:
    - Market Regime & Trend Strength (ADX, +DI, -DI): 30 points
    - Technical Momentum (EMA cross, Daily Trend, RSI): 25 points
    - Volatility & Squeeze Health (ATR Ratio, BB Width): 25 points
    - Portfolio Risk Allowance (Risk Manager): 20 points
    """
    scores = {
        "regime_score": 0.0,
        "momentum_score": 0.0,
        "volatility_score": 0.0,
        "risk_score": 0.0
    }

    if isinstance(regime_info, str):
        regime_info = {"regime": regime_info}
    elif not isinstance(regime_info, dict):
        regime_info = {}

    if not isinstance(technical_indicators, dict):
        technical_indicators = {}

    if not isinstance(risk_eval, dict):
        risk_eval = {}

    regime = regime_info.get("regime", "UNKNOWN")
    adx = float(regime_info.get("adx", 0.0))
    plus_di = float(regime_info.get("plus_di", 0.0))
    minus_di = float(regime_info.get("minus_di", 0.0))
    
    # التعامل مع السجلات التاريخية أو الحقول غير المتوفرة بقيم محايدة
    bb_val = regime_info.get("bb_width")
    bb_width = float(bb_val) if bb_val is not None else 0.04
    
    atr_val = regime_info.get("atr_ratio")
    atr_ratio = float(atr_val) if atr_val is not None else 1.0

    # 1. Regime & Trend Strength (30 pts)
    if regime == "TRENDING_UP" and (plus_di >= minus_di or adx >= 20.0):
        scores["regime_score"] = 30.0
    elif adx >= 22.0 and plus_di > minus_di and regime != "TRENDING_DOWN":
        scores["regime_score"] = 25.0
    elif regime == "SIDEWAYS":
        scores["regime_score"] = 5.0
    else:  # TRENDING_DOWN or plus_di <= minus_di
        scores["regime_score"] = 0.0

    # 2. Technical Momentum (25 pts)
    cross_up = technical_indicators.get("cross_up", False)
    daily_up = technical_indicators.get("daily_up", False)
    rsi_val = technical_indicators.get("rsi_val", 50.0)

    mom_pts = 0.0
    if cross_up: mom_pts += 10.0
    if daily_up: mom_pts += 10.0
    if 45.0 <= rsi_val <= 68.0:
        mom_pts += 5.0
    elif 40.0 <= rsi_val:
        mom_pts += 2.5
    scores["momentum_score"] = mom_pts

    # 3. Volatility & Squeeze Health (25 pts)
    vol_pts = 0.0
    # Squeeze check: avoid squeeze < 0.03
    if bb_width >= 0.03:
        vol_pts += 15.0
    else:
        vol_pts += 0.0  # Squeeze penalty!

    # ATR Ratio check: healthy between 0.8 and 1.4
    if 0.8 <= atr_ratio <= 1.4:
        vol_pts += 10.0
    elif atr_ratio <= 1.6:
        vol_pts += 5.0
    else: # atr_ratio > 1.6 (exhaustion)
        vol_pts += 0.0
    scores["volatility_score"] = vol_pts

    # 4. Risk Allowance (20 pts)
    if risk_eval.get("allowed", False):
        scores["risk_score"] = 20.0
    else:
        scores["risk_score"] = 0.0

    total_score = sum(scores.values())

    # Filter Decisions
    regime_passed = (scores["regime_score"] >= 25.0) and (regime != "TRENDING_DOWN") and (plus_di >= minus_di or adx >= 22.0)
    volatility_passed = (bb_width >= 0.03) and (atr_ratio <= 1.6)
    score_passed = total_score >= 80.0

    is_qds_buy = regime_passed and volatility_passed and score_passed and (cross_up or technical_indicators.get("is_holding", False))

    reasons = []
    if not regime_passed:
        reasons.append(f"فلتر الاتجاه: السوق {regime} (ADX: {adx:.1f}, +DI: {plus_di:.1f} vs -DI: {minus_di:.1f})")
    if not volatility_passed:
        if bb_width < 0.03:
            reasons.append(f"فلتر الانضغاط: BB Width ({bb_width:.4f}) في نطاق خانق")
        if atr_ratio > 1.6:
            reasons.append(f"فلتر التقلب: ATR Ratio ({atr_ratio:.2f}) إجهاد مفرط")
    if total_score < 80.0:
        reasons.append(f"الدرجة المركبة ({total_score:.1f}/100) أقل من 80")

    return {
        "total_score": round(total_score, 1),
        "score_breakdown": scores,
        "regime_passed": regime_passed,
        "volatility_passed": volatility_passed,
        "score_passed": score_passed,
        "is_qds_buy": is_qds_buy,
        "filter_rejection_reasons": reasons
    }