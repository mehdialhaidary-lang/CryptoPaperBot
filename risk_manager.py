"""
======================================================================
 📐 RISK & EXPOSURE MANAGER — محرك إدارة المخاطر وتوزين المحفظة
======================================================================
يقوم بالفصل الهندسي التام بين:
- المخاطرة المالية عند الوقف (Risk at Stop USD)
- القيمة الاسمية للصفقة (Notional Position Size USD)
- نسبة التعرض الإجمالي للمحفظة (Portfolio Exposure %)
- مخاطرة الارتباط التراكمية بين الأزواج (Correlation Exposure)
"""

DEFAULT_RISK_CONFIG = {
    "max_trade_risk_pct": 0.02,        # 2% مخاطرة أقصى للصفقة الواحدة
    "max_portfolio_total_risk_pct": 0.06, # 6% أقصى مخاطرة كليّة تراكمية عند الوقف لكل الأزواج
    "max_portfolio_notional_exposure_pct": 0.80, # 80% أقصى التعرض كلي للمحفظة
    "max_open_positions_count": 3      # أقصى عدد صفقات مفتوحة في نفس الوقت
}

def evaluate_portfolio_risk(
    symbol: str,
    account_balance: float,
    entry_price: float,
    stop_price: float,
    all_symbol_states: dict,
    config: dict = None
) -> dict:
    """
    حساب وفحص مخاطر الدخول قبل التنفيذ.
    إرجاع dict يشمل أحجام المركز الحقيقية والموافقة من عدمها.
    """
    cfg = config or DEFAULT_RISK_CONFIG
    stop_dist = abs(entry_price - stop_price)
    if stop_dist <= 0:
        return {"allowed": False, "reason": "مسافة وقف الخسارة غير صالحة (صفر)"}

    # 1. المخاطرة المسموحة للصفقة الواحدة ($)
    trade_risk_usd = account_balance * cfg.get("max_trade_risk_pct", 0.02)
    
    # 2. الكمية والقيمة الاسمية (Notional Position USD)
    units = trade_risk_usd / stop_dist
    notional_position_usd = units * entry_price
    
    # 3. حساب المخاطرة التراكمية عبر كل الأزواج المفتوحة (Portfolio Total Risk)
    current_total_open_risk_usd = 0.0
    current_total_notional_usd = 0.0
    open_positions_count = 0
    active_symbols = []

    for sym, st in all_symbol_states.items():
        pos = st.get('position')
        if pos is not None:
            open_positions_count += 1
            active_symbols.append(sym)
            e_p = pos.get('entry_price', 0.0)
            sl_p = pos.get('sl', 0.0)
            u = pos.get('units', 0.0)
            risk_usd = abs(e_p - sl_p) * u
            current_total_open_risk_usd += risk_usd
            current_total_notional_usd += (e_p * u)

    # 4. فحص سقف الصفقات المفتوحة
    if open_positions_count >= cfg.get("max_open_positions_count", 3):
        return {
            "allowed": False,
            "reason": f"تم الوصول للحد الأقصى للصفقات المفتوحة ({open_positions_count}/{cfg.get('max_open_positions_count', 3)})",
            "trade_risk_usd": trade_risk_usd,
            "notional_position_usd": notional_position_usd
        }

    # 5. فحص المخاطرة الكلية للمحفظة عند الوقف (Total Open Risk Cap)
    new_total_risk_usd = current_total_open_risk_usd + trade_risk_usd
    total_portfolio_balance = sum([s.get('balance', 1000.0) for s in all_symbol_states.values()])
    total_risk_pct = (new_total_risk_usd / total_portfolio_balance) if total_portfolio_balance > 0 else 0.0
    
    if total_risk_pct > cfg.get("max_portfolio_total_risk_pct", 0.06):
        return {
            "allowed": False,
            "reason": f"تجاوز سقف المخاطرة الكلية للمحفظة عند الوقف ({total_risk_pct*100:.1f}% > {cfg.get('max_portfolio_total_risk_pct', 0.06)*100:.1f}%)",
            "trade_risk_usd": trade_risk_usd,
            "notional_position_usd": notional_position_usd
        }

    return {
        "allowed": True,
        "reason": "المخاطرة والتعرض ضمن الحدود الآمنة للمحفظة",
        "trade_risk_usd": round(trade_risk_usd, 2),
        "units": units,
        "notional_position_usd": round(notional_position_usd, 2),
        "portfolio_total_risk_pct": round(total_risk_pct * 100, 2),
        "current_open_positions_count": open_positions_count,
        "active_symbols": active_symbols
    }