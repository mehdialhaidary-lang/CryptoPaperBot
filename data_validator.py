"""
======================================================================
 🔍 DATA VALIDATOR MODULE — وحدة فحص وتدقيق جودة البيانات
======================================================================
تفحص بيانات الشموع (OHLCV) للتأكد من عدم وجود قيم مفقودة (NaNs)
أو فجوات زمنية (Gaps) أو أسعار صفرية/شاذة قبل تمريرها للنظام.
"""
import pandas as pd
import numpy as np

def validate_ohlcv_dataframe(df: pd.DataFrame, expected_timeframe_hours: int = 4) -> tuple[bool, float, str]:
    """
    فحص جودة بيانات الشموع.
    إرجاع: (is_valid: bool, quality_score: float [0-100], reason: str)
    """
    if df is None or len(df) < 50:
        return False, 0.0, "عدد الشموع غير كافٍ (أقل من 50 شمعة)"

    # 1. فحص القيم المفقودة (NaNs)
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in required_cols:
        if col not in df.columns:
            return False, 0.0, f"العمود المطلوبة مفقود: {col}"
        if df[col].isnull().any():
            return False, 0.0, f"يوجد قيم مفقودة (NaN) في عمود {col}"

    # 2. فحص الأسعار الصفرية أو السالبة
    if (df[['open', 'high', 'low', 'close']] <= 0).any().any():
        return False, 0.0, "تم اكتشاف أسعار صفرية أو سالبة شاذة"

    # 3. فحص التنسيق المنطقي للشموع (High >= Low, High >= Open/Close)
    invalid_candles = (df['high'] < df['low']) | (df['high'] < df['open']) | (df['high'] < df['close'])
    if invalid_candles.any():
        return False, 0.0, "تم اكتشاف شموع غير منطقية (High < Low أو High < Close)"

    # 4. فحص الفجوات الزمنية (Gaps Check)
    if 'timestamp' in df.columns:
        df_ts = df['timestamp'].astype(np.int64)
        diffs = df_ts.diff().dropna()
        expected_ms = expected_timeframe_hours * 3600 * 1000
        # نتحقق إذا كانت الفجوات تتجاوز 1.5 ضعف الفريم المكتوب
        gaps = diffs[diffs > expected_ms * 1.5]
        if len(gaps) > 0:
            quality_score = max(0.0, 100.0 - (len(gaps) * 10.0))
            return True, quality_score, f"تم اكتشاف {len(gaps)} فجوات زمنية في البيانات"

    return True, 100.0, "البيانات سليمة 100%"