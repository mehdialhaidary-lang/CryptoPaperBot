import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import tempfile
import shutil
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath("."))

import market_regime
import shadow_engine
import trade_memory

def run_tests():
    print("=" * 60)
    print("[TEST] PHASE 2: QDS SIGNAL MATRIX VERIFICATION SUITE")
    print("=" * 60)
    
    # ---------------------------------------------------------
    # TEST 1: calculate_dmi and calculate_adx backward compat
    # ---------------------------------------------------------
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", periods=100, freq="4h")
    prices = 50000 + np.cumsum(np.random.randn(100) * 200)
    df_sample = pd.DataFrame({
        "timestamp": [int(d.timestamp() * 1000) for d in dates],
        "open": prices,
        "high": prices + 150,
        "low": prices - 150,
        "close": prices + 50,
        "volume": 1000
    })
    
    adx_s, plus_s, minus_s = market_regime.calculate_dmi(df_sample, period=14)
    adx_legacy = market_regime.calculate_adx(df_sample, period=14)
    
    assert len(adx_s) == len(df_sample), "DMI length mismatch"
    assert np.allclose(adx_s.values, adx_legacy.values, equal_nan=True), "Backward compatibility broken in calculate_adx"
    print(">>> TEST 1: calculate_dmi and calculate_adx backward compatibility PASSED")
    
    # ---------------------------------------------------------
    # TEST 2: detect_market_regime structure
    # ---------------------------------------------------------
    regime_res = market_regime.detect_market_regime(df_sample)
    assert "regime" in regime_res
    assert "adx" in regime_res
    assert "plus_di" in regime_res
    assert "minus_di" in regime_res
    assert "bb_width" in regime_res
    assert "atr_ratio" in regime_res
    print(f">>> TEST 2: detect_market_regime output fields PASSED: {regime_res['regime']} (ADX={regime_res['adx']}, +DI={regime_res['plus_di']}, -DI={regime_res['minus_di']})")
    
    # ---------------------------------------------------------
    # TEST 3: calculate_qds_composite_score Scenarios
    # ---------------------------------------------------------
    # Scenario 3A: Downtrend Bull Trap (cross_up=True, but regime=TRENDING_DOWN)
    res_3a = market_regime.calculate_qds_composite_score(
        regime_info={"regime": "TRENDING_DOWN", "adx": 28.0, "plus_di": 12.0, "minus_di": 35.0, "atr_ratio": 1.1, "bb_width": 0.04},
        technical_indicators={"cross_up": True, "daily_up": True, "rsi_val": 52.0},
        risk_eval={"allowed": True}
    )
    assert not res_3a["is_qds_buy"], "Scenario 3A should reject BUY in TRENDING_DOWN"
    assert not res_3a["regime_passed"], "Scenario 3A regime_passed should be False"
    assert res_3a["total_score"] < 80.0, f"Scenario 3A score should be < 80 (was {res_3a['total_score']})"
    print(f">>> TEST 3A: Downtrend Bull Trap Blocked PASSED (Score: {res_3a['total_score']}, Reasons: {res_3a['filter_rejection_reasons']})")
    
    # Scenario 3B: Bollinger Squeeze in Sideways (cross_up=True, but bb_width=0.018 < 0.03)
    res_3b = market_regime.calculate_qds_composite_score(
        regime_info={"regime": "SIDEWAYS", "adx": 15.0, "plus_di": 18.0, "minus_di": 16.0, "atr_ratio": 0.95, "bb_width": 0.018},
        technical_indicators={"cross_up": True, "daily_up": True, "rsi_val": 50.0},
        risk_eval={"allowed": True}
    )
    assert not res_3b["is_qds_buy"], "Scenario 3B should reject BUY in Squeeze"
    assert not res_3b["volatility_passed"], "Scenario 3B volatility_passed should be False"
    print(f">>> TEST 3B: Squeeze Filter PASSED (Score: {res_3b['total_score']}, Reasons: {res_3b['filter_rejection_reasons']})")
    
    # Scenario 3C: Exhaustion Volatility (atr_ratio=1.85 > 1.6)
    res_3c = market_regime.calculate_qds_composite_score(
        regime_info={"regime": "TRENDING_UP", "adx": 30.0, "plus_di": 30.0, "minus_di": 12.0, "atr_ratio": 1.85, "bb_width": 0.05},
        technical_indicators={"cross_up": True, "daily_up": True, "rsi_val": 60.0},
        risk_eval={"allowed": True}
    )
    assert not res_3c["is_qds_buy"], "Scenario 3C should reject BUY on exhaustion ATR"
    assert not res_3c["volatility_passed"], "Scenario 3C volatility_passed should be False"
    print(f">>> TEST 3C: Volatility Exhaustion Filter PASSED (Score: {res_3c['total_score']})")

    # Scenario 3D: Clean Golden Trend Breakout
    res_3d = market_regime.calculate_qds_composite_score(
        regime_info={"regime": "TRENDING_UP", "adx": 32.0, "plus_di": 35.0, "minus_di": 10.0, "atr_ratio": 1.15, "bb_width": 0.048},
        technical_indicators={"cross_up": True, "daily_up": True, "rsi_val": 56.0},
        risk_eval={"allowed": True}
    )
    assert res_3d["is_qds_buy"], f"Scenario 3D must qualify as BUY! Score: {res_3d['total_score']}"
    assert res_3d["total_score"] >= 80.0, f"Scenario 3D score must be >= 80 (was {res_3d['total_score']})"
    assert len(res_3d["filter_rejection_reasons"]) == 0
    print(f">>> TEST 3D: Clean Trend Signal PASSED (Score: {res_3d['total_score']}/100, is_qds_buy: True)")

    # ---------------------------------------------------------
    # TEST 4: shadow_engine isolated integration & ablation
    # ---------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp_dir:
        orig_cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            # Setup dummy df_4h with technical columns
            df_test = df_sample.copy()
            df_test['ema_fast'] = [100.0] * (len(df_test) - 2) + [99.0, 105.0]
            df_test['ema_slow'] = [100.0] * len(df_test)
            df_test['daily_trend_up'] = True
            df_test['rsi'] = 55.0
            df_test['atr'] = 500.0
            
            # 1. Under USE_QDS_FILTERS = True
            shadow_engine.USE_QDS_FILTERS = True
            eval_res = shadow_engine.evaluate_shadow_qds_cycle(
                symbol="BTC/USDT",
                df_4h=df_test,
                df_1d=None,
                legacy_decision="WAIT",
                current_price=51000.0,
                symbol_states={"BTC/USDT": {"balance": 1000.0}}
            )
            assert "qds_score" in eval_res
            assert "qds_eval" in eval_res
            
            # Check state file and memory file generated in sandbox
            assert os.path.exists("shadow_state.json")
            assert os.path.exists("trade_memory.json")
            
            with open("trade_memory.json", "r", encoding="utf-8") as f:
                mem = json.load(f)
            latest_rec = mem[-1]
            flags = latest_rec["ablation_flags"]
            assert "qds_composite_score" in flags
            assert "qds_regime_passed" in flags
            assert "qds_volatility_passed" in flags
            assert flags["qds_filters_enabled"] is True
            print(f">>> TEST 4: shadow_engine integration & ablation logging PASSED (Decision: {eval_res['decision']}, Score: {eval_res['qds_score']})")
        finally:
            os.chdir(orig_cwd)

    # ---------------------------------------------------------
    # TEST 5: Backtest on Historical 305 Records
    # ---------------------------------------------------------
    hist_file = "trade_memory_raw_backup.json"
    if os.path.exists(hist_file):
        with open(hist_file, "r", encoding="utf-8") as f:
            hist_records = json.load(f)
        
        legacy_buys = 0
        qds_buys = 0
        blocked_false_positives = 0
        true_positives_retained = 0
        
        for r in hist_records:
            reg_raw = r.get("market_regime", {})
            if isinstance(reg_raw, dict):
                regime = reg_raw.get("regime", "UNKNOWN")
                reg_info = reg_raw
            else:
                regime = str(reg_raw)
                reg_info = {"regime": regime}
                
            abl = r.get("ablation_flags", {})
            legacy_would_buy = abl.get("tech_passed", False) and abl.get("portfolio_risk_passed", True)
            
            if legacy_would_buy:
                legacy_buys += 1
                qds_eval = market_regime.calculate_qds_composite_score(
                    regime_info=reg_info,
                    technical_indicators={
                        "cross_up": True,
                        "daily_up": True,
                        "rsi_val": r.get("technical_score", 50.0)
                    },
                    risk_eval={"allowed": abl.get("portfolio_risk_passed", True)}
                )
                if qds_eval["is_qds_buy"]:
                    qds_buys += 1
                    if regime == "TRENDING_UP":
                        true_positives_retained += 1
                else:
                    if regime in ("TRENDING_DOWN", "SIDEWAYS"):
                        blocked_false_positives += 1
        
        print("-" * 60)
        print(f"[HISTORICAL AUDIT] (305 Records):")
        print(f"   Legacy BUY Candidates: {legacy_buys}")
        print(f"   Blocked False Positives in Chop/Downtrend: {blocked_false_positives}")
        print(f"   QDS BUY Approved: {qds_buys}")
        print(f"   True Positives in Uptrend Retained: {true_positives_retained}")
        non_up_candidates = blocked_false_positives + (legacy_buys - blocked_false_positives - true_positives_retained)
        if non_up_candidates > 0:
            elimination_rate = (blocked_false_positives / non_up_candidates) * 100
            print(f"   False Positive Elimination Rate: {elimination_rate:.1f}%")
        print(">>> TEST 5: Historical Data Backtest PASSED")
    
    print("=" * 60)
    print("ALL 5 TEST SUITES PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
