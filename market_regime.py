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

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """حساب مؤشر ADX لتحديد قوة الاتجاه."""
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
    return adx.fillna(0.0)

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
    
    # 1. ADX
    adx_series = calculate_adx(df_4h, period=cfg.get("adx_period", 14))
    current_adx = float(adx_series.iloc[-2])
    
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
        if c.get('ema_fast', 0) > c.get('ema_slow', 0):
            regime = "TRENDING_UP"
        else:
            regime = "TRENDING_DOWN"
    elif current_adx <= cfg.get("adx_sideways_threshold", 18.0) or bb_width <= cfg.get("bb_width_squeeze", 0.03):
        regime = "SIDEWAYS"
    elif atr_ratio >= cfg.get("atr_ratio_high_vol", 1.4):
        regime = "HIGH_VOLATILITY"
    elif atr_ratio <= cfg.get("atr_ratio_low_vol", 0.7):
        regime = "LOW_VOLATILITY"

    return {
        "regime": regime,
        "adx": round(current_adx, 2),
        "atr_ratio": round(atr_ratio, 2),
        "bb_width": round(bb_width, 4),
        "is_trending": "TRENDING" in regime,
        "details": f"ADX: {current_adx:.1f} | ATR Ratio: {atr_ratio:.2f} | BB Width: {bb_width:.3f}"
    }