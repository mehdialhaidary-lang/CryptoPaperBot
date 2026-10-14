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
SHADOW_STATE_FILE = "shadow_state.json"

def load_trade_memory(memory_file: str = MEMORY_FILE) -> list:
    """قراءة سجل ذاكرة الصفقات التراكمي."""
    if os.path.exists(memory_file):
        try:
            with open(memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_trade_memory(records: list, memory_file: str = MEMORY_FILE):
    """حفظ ذاكرة الصفقات التراكمية بكفاءة ذرية."""
    tmp = memory_file + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=4, default=str, ensure_ascii=False)
    os.replace(tmp, memory_file)

def load_shadow_state(state_file: str = SHADOW_STATE_FILE) -> dict:
    """قراءة حالة الظل وملف التعليقات والشذوذ."""
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'suspended_records': {}, 'anomalies': [], 'untracked_historical_trades': []}

def save_shadow_state(state: dict, state_file: str = SHADOW_STATE_FILE):
    """حفظ حالة الظل بشكل ذري وآمن."""
    tmp = state_file + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4, default=str, ensure_ascii=False)
    os.replace(tmp, state_file)

def compute_record_uid(record: dict) -> str:
    """اشتقاق المعرف الفريد الثابت للسجل مع دعم التوليد التشفيري والسجلات القديمة."""
    uid = record.get('record_uid')
    if uid and isinstance(uid, str) and uid.strip():
        return uid.strip()

    eid = record.get('event_id')
    if eid and isinstance(eid, str) and eid.strip():
        return eid.strip()

    sym = record.get('symbol')
    if not sym or not isinstance(sym, str) or not sym.strip():
        raise ValueError(f"CRITICAL: Record missing mandatory 'symbol': {record}")
    sym_clean = sym.replace('/', '_').strip()

    tid = record.get('trade_id')
    if not tid or not isinstance(tid, str) or not tid.strip():
        raise ValueError(f"CRITICAL: Record missing mandatory 'trade_id': {record}")
    tid_clean = tid.strip()

    ts = record.get('timestamp')
    if not ts or not isinstance(ts, str) or not ts.strip():
        raise ValueError(f"CRITICAL: Record missing mandatory 'timestamp': {record}")

    clean_ts = ts.strip().replace('Z', '+00:00')
    dt = datetime.fromisoformat(clean_ts).astimezone(timezone.utc)
    ts_canonical = dt.strftime('%Y%m%dT%H%M%S_%fZ')

    return f"legacy_{sym_clean}_{tid_clean}_{ts_canonical}"

def compute_cycle_id(symbol: str, entry_time_str: str, entry_price: float) -> tuple:
    """اشتقاق هوية دورة المركز الفريدة بدقة الميكروثانية و8 منازل عشرية للسعر."""
    clean_ts = entry_time_str.strip().replace('Z', '+00:00')
    dt = datetime.fromisoformat(clean_ts).astimezone(timezone.utc)
    epoch_us = int(dt.timestamp() * 1_000_000)
    p_norm = round(float(entry_price), 8)
    sym_clean = symbol.replace('/', '_').strip()
    return (sym_clean, epoch_us, p_norm)

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
    ablation_flags: dict = None,
    legacy_action: str = None,
    position_state: str = None,
    qds_action: str = None
) -> dict:
    """بناء هيكل سجل صفقة جديد ومطابق للمواصفات مع فصل حالة المركز عن إشارة الدخول."""
    leg_action = legacy_action or legacy_decision
    pos_state = position_state or ("LONG" if leg_action in ("BUY", "HOLD") else "FLAT")
    qd_action = qds_action or qds_decision

    default_ablation = {
        "legacy_passed": leg_action == "BUY",
        "tech_passed": technical_score >= 100.0,
        "regime_passed": market_regime.get("is_trending", False),
        "portfolio_risk_passed": risk_data.get("allowed", True),
        "news_ai_passed": gemini_data.get("safe", True)
    }
    
    return {
        "record_version": 2,
        "record_uid": trade_id,
        "event_id": trade_id,
        "trade_id": trade_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "timeframe": "4h",
        "is_candle_close_event": is_candle_close_event,

        # 1. Action & Position State Separation (Phase 1)
        "position_state": pos_state,
        "legacy_action": leg_action,
        "qds_action": qd_action,
        "is_entry_signal": (leg_action == "BUY"),

        # 2. Backward Compatibility Fields (Preserved for existing tools)
        "legacy_decision": legacy_decision,
        "qds_decision": qds_decision,
        
        # 3. Ablation Testing Flags
        "ablation_flags": ablation_flags or default_ablation,

        # 4. Market Regime Metadata
        "market_regime": market_regime.get("regime", "UNKNOWN") if isinstance(market_regime, dict) else str(market_regime),
        "adx": market_regime.get("adx", 0.0) if isinstance(market_regime, dict) else 0.0,
        "plus_di": market_regime.get("plus_di", 0.0) if isinstance(market_regime, dict) else 0.0,
        "minus_di": market_regime.get("minus_di", 0.0) if isinstance(market_regime, dict) else 0.0,
        "atr_ratio": market_regime.get("atr_ratio", 1.0) if isinstance(market_regime, dict) else 1.0,
        "bb_width": market_regime.get("bb_width", 0.0) if isinstance(market_regime, dict) else 0.0,
        
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
        "exit_reason": "NONE" if (legacy_decision == "WAIT" and qds_decision == "WAIT") else "PENDING",
        "status": "OPEN" if (legacy_decision == "BUY" or qds_decision == "BUY") else "CLOSED",
        "outcome": "PENDING" if (legacy_decision == "BUY" or qds_decision == "BUY") else "SKIPPED",
        
        # PnL Accounting Breakdown
        "gross_pnl_usd": 0.0,
        "fees_usd": 0.0,
        "slippage_usd": 0.0,
        "net_pnl_usd": 0.0,
        "pnl_usd": 0.0,  # alias for net_pnl_usd
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

def calculate_pnl_breakdown(
    entry_price: float,
    exit_price: float,
    units: float,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    spread_pct: float = 0.0002
) -> dict:
    """حسبة دقيقة وشفافة للربح/الخسارة مفصلة إلى Gross و Fees و Slippage و Net."""
    if entry_price <= 0 or units <= 0:
        return {"gross_pnl_usd": 0.0, "fees_usd": 0.0, "slippage_usd": 0.0, "net_pnl_usd": 0.0, "pnl_pct": 0.0}

    notional_entry = entry_price * units
    notional_exit  = exit_price * units
    
    gross_pnl_usd = notional_exit - notional_entry
    slippage_usd  = (notional_entry + notional_exit) * (slippage_pct + spread_pct)
    fees_usd      = (notional_entry + notional_exit) * commission_pct
    net_pnl_usd   = gross_pnl_usd - slippage_usd - fees_usd
    pnl_pct       = (net_pnl_usd / notional_entry) * 100.0 if notional_entry > 0 else 0.0

    return {
        "gross_pnl_usd": round(gross_pnl_usd, 4),
        "fees_usd": round(fees_usd, 4),
        "slippage_usd": round(slippage_usd, 4),
        "net_pnl_usd": round(net_pnl_usd, 4),
        "pnl_pct": round(pnl_pct, 4)
    }

def record_decision_event(record: dict):
    """إضافة سجل صفقة جديد إلى الذاكرة وإبقاؤه في التزامن."""
    memory = load_trade_memory()
    memory.append(record)
    save_trade_memory(memory)

def update_open_records_excursions(symbol: str, current_price: float, memory_file: str = MEMORY_FILE, state_file: str = SHADOW_STATE_FILE) -> int:
    """تحديث رحلة السعر المستقلة (MFE/MAE والآفاق الزمنية 4h/12h/24h/48h) لجميع القرارات المسجلة غير المعلقة."""
    memory = load_trade_memory(memory_file)
    shadow_st = load_shadow_state(state_file)
    suspended = shadow_st.get('suspended_records', {})

    updated = False
    updated_count = 0
    now = datetime.now(timezone.utc)

    for rec in memory:
        if rec.get("symbol") != symbol:
            continue
        
        try:
            uid = compute_record_uid(rec)
        except Exception:
            continue

        if uid in suspended:
            # تعليق صارم: تجميد القياسات لمنع تشويه المخاطر
            continue

        status = rec.get("legacy_status") or rec.get("status")
        if status != "OPEN":
            continue

        entry = rec.get("entry_price") or rec.get("hypothetical_entry") or rec.get("stop_loss_price") or 0.0
        if entry <= 0.0:
            continue

        rec_time_str = rec.get("timestamp", "")
        try:
            clean_ts = rec_time_str.strip().replace('Z', '+00:00')
            rec_time = datetime.fromisoformat(clean_ts).astimezone(timezone.utc)
            elapsed_hours = (now - rec_time).total_seconds() / 3600.0
        except Exception:
            elapsed_hours = 0.0

        pnl_pct = ((current_price - entry) / entry) * 100.0

        # تحديث MFE & MAE
        if "legacy_mfe_pct" in rec:
            if pnl_pct > rec.get("legacy_mfe_pct", 0.0):
                rec["legacy_mfe_pct"] = round(pnl_pct, 2)
                updated = True
            if pnl_pct < rec.get("legacy_mae_pct", 0.0):
                rec["legacy_mae_pct"] = round(pnl_pct, 2)
                updated = True
        else:
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

        updated_count += 1

    if updated:
        save_trade_memory(memory, memory_file)

    return updated_count

def link_and_close_exit(symbol: str, exit_trade: dict, memory_file: str = MEMORY_FILE, state_file: str = SHADOW_STATE_FILE) -> bool:
    """ربط وإغلاق صفقة خروج مع السجل المفتوح المطابق في CycleID مع رصد التصادم وتعليقه."""
    memory = load_trade_memory(memory_file)
    shadow_st = load_shadow_state(state_file)
    suspended = shadow_st.setdefault('suspended_records', {})
    anomalies = shadow_st.setdefault('anomalies', [])

    exit_time = exit_trade.get('entry_time')
    exit_entry_price = exit_trade.get('entry_price')
    actual_exit_price = exit_trade.get('exit_price')

    if not exit_time or exit_entry_price is None or actual_exit_price is None or actual_exit_price <= 0:
        anomalies.append(f'INVALID_EXIT_DATA_FOR_LINKING: {exit_trade}')
        save_shadow_state(shadow_st, state_file)
        return False

    try:
        exit_cycle_id = compute_cycle_id(symbol, exit_time, exit_entry_price)
    except Exception as e:
        anomalies.append(f'CYCLE_ID_COMPUTATION_FAILED: {exit_trade} (Error: {e})')
        save_shadow_state(shadow_st, state_file)
        return False

    candidates = []
    for rec in memory:
        if rec.get('symbol') != symbol:
            continue
        status = rec.get('legacy_status') or rec.get('status')
        if status != 'OPEN':
            continue

        r_time = rec.get('position_entry_time') or rec.get('timestamp')
        r_price = rec.get('entry_price') or 0.0
        try:
            r_cid = compute_cycle_id(symbol, r_time, r_price)
        except Exception:
            continue

        if r_cid == exit_cycle_id:
            candidates.append(rec)

    if len(candidates) == 0:
        anomalies.append(f'NO_OPEN_RECORD_MATCHING_EXIT: CycleID={exit_cycle_id}')
        save_shadow_state(shadow_st, state_file)
        return False

    if len(candidates) > 1:
        # تصادم صريح: حظر الإغلاق بالتخمين وتعليق السجلات وتجميد القياسات
        msg = f'CYCLE_ID_COLLISION_ANOMALY: {len(candidates)} records share CycleID {exit_cycle_id}. Exit linking aborted.'
        anomalies.append(msg)
        for cand in candidates:
            c_uid = compute_record_uid(cand)
            suspended[c_uid] = {
                'reason': 'CYCLE_ID_COLLISION_SUSPENDED',
                'cycle_id': str(exit_cycle_id),
                'detected_at': datetime.now(timezone.utc).isoformat(),
                'action': 'EXIT_LINKING_BLOCKED_EXCURSIONS_FROZEN'
            }
        save_shadow_state(shadow_st, state_file)
        return False

    matched_rec = candidates[0]
    matched_uid = compute_record_uid(matched_rec)
    if matched_uid in suspended:
        anomalies.append(f'LINKING_ABORTED_SUSPENDED_RECORD: {matched_uid}')
        save_shadow_state(shadow_st, state_file)
        return False

    matched_rec['legacy_status'] = 'CLOSED'
    matched_rec['status'] = 'CLOSED'
    matched_rec['exit_price'] = actual_exit_price
    matched_rec['exit_time'] = exit_trade.get('exit_time')
    matched_rec['pnl_usd'] = exit_trade.get('pnl', 0.0)
    save_trade_memory(memory, memory_file)
    return True

def reconcile_open_records_on_startup(symbol: str, paper_state: dict, memory_file: str = MEMORY_FILE, state_file: str = SHADOW_STATE_FILE) -> dict:
    """مصالحة السجلات المفتوحة عند الإقلاع واسترداد المراكز الحية السليمة غير المسجلة مع حظر الازدواجية والتعليق عند التعارض."""
    memory = load_trade_memory(memory_file)
    shadow_st = load_shadow_state(state_file)
    suspended = shadow_st.setdefault('suspended_records', {})
    anomalies = shadow_st.setdefault('anomalies', [])

    live_pos = paper_state.get('position')
    trades = paper_state.get('trades', [])

    results = {'recovered_entries': 0, 'closed_trades': 0, 'suspended_cycles': 0}

    if live_pos is not None:
        p_time = live_pos.get('entry_time')
        p_price = live_pos.get('entry_price')

        if not p_time or p_price is None or p_price <= 0:
            anomalies.append(f'INSUFFICIENT_ENTRY_DATA_FOR_CYCLE_ID: {live_pos}')
            pos_key = f'live_{symbol}_{p_time}'
            suspended[pos_key] = {'reason': 'INSUFFICIENT_ENTRY_DATA_FOR_CYCLE_ID', 'data': live_pos}
            results['suspended_cycles'] += 1
        else:
            live_cid = compute_cycle_id(symbol, p_time, p_price)

            contradicting_closed = [t for t in trades if compute_cycle_id(symbol, t.get('entry_time', ''), t.get('entry_price', 0.0)) == live_cid]
            if len(contradicting_closed) > 0:
                anomalies.append(f'STATE_CORRUPTION_POSITION_TRADES_CONTRADICTION: CycleID {live_cid}')
                suspended[f'contradiction_{symbol}_{live_cid[1]}'] = {'reason': 'STATE_CORRUPTION_POSITION_TRADES_CONTRADICTION', 'cycle_id': str(live_cid)}
                results['suspended_cycles'] += 1
            else:
                matching = []
                for rec in memory:
                    if rec.get('symbol') != symbol:
                        continue
                    r_time = rec.get('position_entry_time') or rec.get('timestamp')
                    r_price = rec.get('entry_price') or 0.0
                    try:
                        if compute_cycle_id(symbol, r_time, r_price) == live_cid:
                            matching.append(rec)
                    except Exception:
                        pass

                if len(matching) > 1:
                    anomalies.append(f'CYCLE_ID_COLLISION_ANOMALY: {len(matching)} records match live CycleID {live_cid}')
                    for m in matching:
                        m_uid = compute_record_uid(m)
                        suspended[m_uid] = {'reason': 'CYCLE_ID_COLLISION_SUSPENDED', 'cycle_id': str(live_cid)}
                    results['suspended_cycles'] += 1
                elif len(matching) == 0:
                    new_uid = f"rec_v2_{symbol.replace('/', '_')}_ENTRY_{live_cid[1]}"
                    new_rec = {
                        'record_uid': new_uid,
                        'event_id': new_uid,
                        'record_version': 2,
                        'symbol': symbol,
                        'position_entry_time': p_time,
                        'entry_price': p_price,
                        'stop_loss_price': live_pos.get('sl', 0.0),
                        'take_profit_price': live_pos.get('tp', 0.0),
                        'legacy_status': 'OPEN',
                        'status': 'OPEN',
                        'is_entry_signal': True,
                        'reconciliation_status': 'RECOVERED_LIVE_ENTRY',
                        'legacy_mfe_pct': 0.0,
                        'legacy_mae_pct': 0.0,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    memory.append(new_rec)
                    save_trade_memory(memory, memory_file)
                    results['recovered_entries'] += 1

    save_shadow_state(shadow_st, state_file)
    return results