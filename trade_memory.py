"""
======================================================================
 💾 TRADE MEMORY MASTER SCHEMA — قاعدة بيانات ذاكرة الصفقات الموسعة
======================================================================
تحفظ السجل الشامل لكل قرار (حقيقي أو ظلي) مع كافة القياسات الحيوية:
MFE (Max Favorable Excursion), MAE (Max Adverse Excursion),
حالة السوق، تقييم الأخبار، المخاطرة الكلية، والافتراضيات المقارنة.
"""
import json
import os
from datetime import datetime, timezone

MEMORY_FILE = "trade_memory.json"

def load_trade_memory() -> list:
    """قراءة سجل ذاكرة الصفقات التراكمي."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_trade_memory(records: list):
    """حفظ ذاكرة الصفقات التراكمية بكفاءة."""
    tmp = MEMORY_FILE + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=4, default=str, ensure_ascii=False)
    os.replace(tmp, MEMORY_FILE)

def build_trade_record(
    trade_id: str,
    symbol: str,
    legacy_decision: str,
    qds_decision: str,
    market_regime: dict,
    technical_score: float,
    gemini_data: dict,
    risk_data: dict,
    data_quality: dict,
    decision_reason: str,
    wait_reason: str = "",
    entry_price: float = 0.0,
    hypothetical_entry: float = 0.0,
    stop_loss_price: float = 0.0,
    take_profit_price: float = 0.0,
    is_candle_close_event: bool = False,
    ablation_flags: dict = None
) -> dict:
    """بناء هيكل سجل صفقة جديد ومطابق للمواصفات المستقبلية بـ Ablation Flags و Disambiguation."""
    default_ablation = {
        "legacy_passed": legacy_decision == "BUY",
        "tech_passed": technical_score >= 100.0,
        "regime_passed": market_regime.get("is_trending", False),
        "portfolio_risk_passed": risk_data.get("allowed", True),
        "news_ai_passed": gemini_data.get("safe", True)
    }
    
    return {
        "trade_id": trade_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "timeframe": "4h",
        "is_candle_close_event": is_candle_close_event,
        "legacy_decision": legacy_decision,
        "qds_decision": qds_decision,
        
        # 1. Ablation Testing Flags
        "ablation_flags": ablation_flags or default_ablation,

        # 2. Market Regime Metadata
        "market_regime": market_regime.get("regime", "UNKNOWN"),
        "adx": market_regime.get("adx", 0.0),
        "atr_ratio": market_regime.get("atr_ratio", 1.0),
        "bb_width": market_regime.get("bb_width", 0.0),
        
        # 3. Scores & AI Metadata
        "technical_score": round(technical_score, 2),
        "news_score": gemini_data.get("sentiment_score", 0.0),
        "news_impact": gemini_data.get("impact", "LOW"),
        "news_confidence": gemini_data.get("confidence", 0.0),
        "news_novelty": gemini_data.get("novelty", 0.5),
        "source_quality": gemini_data.get("source_quality", "STANDARD"),
        "gemini_status": gemini_data.get("status", "NOT_CONFIGURED"),
        
        # 4. Risk & Position Sizing Metadata
        "risk_at_stop_usd": risk_data.get("trade_risk_usd", 0.0),
        "notional_position_usd": risk_data.get("notional_position_usd", 0.0),
        "portfolio_exposure_pct": risk_data.get("portfolio_total_risk_pct", 0.0),
        "correlation_risk_pct": 0.0,
        
        # 5. Data Quality
        "data_quality_score": data_quality.get("score", 100.0),
        "data_quality_status": data_quality.get("status", "OK"),
        
        # 6. Decision Rationale
        "decision_reason": decision_reason,
        "wait_reason": wait_reason,
        
        # 7. Trade Execution & Price Tracking
        "entry_price": entry_price,
        "hypothetical_entry": hypothetical_entry,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "exit_price": 0.0,
        "hypothetical_exit": 0.0,
        "status": "OPEN" if (legacy_decision == "BUY" or qds_decision == "BUY") else "CLOSED",
        "outcome": "PENDING" if (legacy_decision == "BUY" or qds_decision == "BUY") else "SKIPPED",
        "pnl_usd": 0.0,
        "pnl_pct": 0.0,
        "duration_hours": 0.0,
        
        # 8. Excursion Analytics (MFE & MAE)
        "mfe_pct": 0.0,  # Maximum Favorable Excursion
        "mae_pct": 0.0,   # Maximum Adverse Excursion

        # 9. Post-Decision Forward Horizons (4h, 12h, 24h, 48h)
        "forward_horizons": {
            "4h": None,
            "12h": None,
            "24h": None,
            "48h": None
        }
    }

def record_decision_event(record: dict):
    """إضافة سجل صفقة جديد إلى الذاكرة وإبقاؤه في التزامن."""
    memory = load_trade_memory()
    memory.append(record)
    save_trade_memory(memory)

def update_open_records_excursions(symbol: str, current_price: float):
    """تحديث رحلة السعر المستقلة (MFE/MAE والآفاق الزمنية 4h/12h/24h/48h) لجميع القرارات المسجلة."""
    memory = load_trade_memory()
    updated = False
    now = datetime.now(timezone.utc)

    for rec in memory:
        if rec.get("symbol") != symbol:
            continue
        
        entry = rec.get("entry_price") or rec.get("hypothetical_entry") or 0.0
        if entry <= 0.0:
            continue

        rec_time_str = rec.get("timestamp", "")
        try:
            rec_time = datetime.fromisoformat(rec_time_str)
            elapsed_hours = (now - rec_time).total_seconds() / 3600.0
        except Exception:
            elapsed_hours = 0.0

        pnl_pct = ((current_price - entry) / entry) * 100.0

        # تحديث MFE & MAE
        if pnl_pct > rec.get("mfe_pct", 0.0):
            rec["mfe_pct"] = round(pnl_pct, 2)
            updated = True
        if pnl_pct < rec.get("mae_pct", 0.0):
            rec["mae_pct"] = round(pnl_pct, 2)
            updated = True

        # تحديث Forward Horizons
        horizons = rec.setdefault("forward_horizons", {"4h": None, "12h": None, "24h": None, "48h": None})
        if elapsed_hours >= 4.0 and horizons.get("4h") is None:
            horizons["4h"] = round(pnl_pct, 2)
            updated = True
        if elapsed_hours >= 12.0 and horizons.get("12h") is None:
            horizons["12h"] = round(pnl_pct, 2)
            updated = True
        if elapsed_hours >= 24.0 and horizons.get("24h") is None:
            horizons["24h"] = round(pnl_pct, 2)
            updated = True
        if elapsed_hours >= 48.0 and horizons.get("48h") is None:
            horizons["48h"] = round(pnl_pct, 2)
            updated = True

    if updated:
        save_trade_memory(memory)