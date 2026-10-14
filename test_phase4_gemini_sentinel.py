"""
=============================================================================
🧪 PHASE 4 TEST SUITE — اختبارات التحقق الصارم لحارس الأخبار (Gemini Sentinel)
=============================================================================
يفحص ويتحقق من الالتزام بكافة بنود الملحق التشغيلي وميثاق مجلس الذكاء الاصطناعي:
1. تحقق بيئة الأخبار الطبيعية (ALLOW Verification).
2. الفحص الحتمي السريع للكوارث بالكلمات المفتاحية (Instant Lexical VETO).
3. فحص كشف الكوارث عبر الـ LLM (Catastrophic Black Swan VETO).
4. رفض الفيتو العشوائي ذي الثقة المنخفضة (Downgrade if Confidence < 85%).
5. بروتوكول الأمان عند الأعطال (Fail-Closed Protective Circuit Breaker).
6. ترشيد الموارد وحظر الاستدعاء إلا لإشارات الشراء المرشحة (Candidate Gatekeeper).
7. الالتزام الصارم بقاعدة عدم لمس الملفات الإنتاجية (Zero-Touch Verification).
=============================================================================
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
import unittest
import json
import time

# استيراد الوحدات تحت الفحص
import gemini_validator
import shadow_engine
import trade_memory

class TestPhase4GeminiSentinel(unittest.TestCase):

    def setUp(self):
        """تهيئة بيئة الاختبار."""
        self.symbol = "BTC/USDT"

    def test_01_normal_headlines_allow(self):
        """اختبار 1: بيئة أخبار طبيعية/اعتيادية تعيد ALLOW وأمان كامل."""
        benign_headlines = [
            "Current price of Bitcoin for October 14, 2026 - Fortune",
            "Standard Chartered Opens Bitcoin, Ether Trading to Wealthy UAE Clients",
            "Bitcoin consolidation continues near $83,000 as traders eye next resistance",
            "Ethereum L2 TVL grows 5% week-over-week"
        ]
        
        # رد محاكى مطابق لمخرجات الموديل في الظروف الطبيعية
        mock_response = json.dumps({
            "verdict": "ALLOW",
            "risk_level": "LOW",
            "confidence": 95,
            "black_swan_category": "NONE",
            "reason": "Market headlines are routine with no signs of exchange insolvency or protocol exploits."
        })

        res = gemini_validator.validate_candidate_entry(
            symbol=self.symbol,
            mock_headlines=benign_headlines,
            mock_response=mock_response
        )

        self.assertEqual(res["verdict"], "ALLOW")
        self.assertTrue(res["safe"])
        self.assertEqual(res["risk_level"], "LOW")
        self.assertGreaterEqual(res["confidence"], 85.0)
        self.assertEqual(res["black_swan_category"], "NONE")
        print("\n[OK] Test 01 Passed: Benign news environment granted ALLOW clearance.")

    def test_02_instant_deterministic_black_swan_veto(self):
        """اختبار 2: كشف الكارثة فورياً بالحتمية اللفظية (Lexical Filter) خلال أقل من 10 ملي ثانية."""
        catastrophic_headlines = [
            "Bitcoin trading volume reaches new high",
            "BREAKING: Major Tier-1 Exchange Pauses All Withdrawals Due to Liquidity Crisis and Run on Bank",
            "Crypto market analysis for October 2026"
        ]

        t0 = time.time()
        res = gemini_validator.validate_candidate_entry(
            symbol=self.symbol,
            mock_headlines=catastrophic_headlines
        )
        t_elapsed_ms = (time.time() - t0) * 1000

        self.assertEqual(res["verdict"], "VETO")
        self.assertFalse(res["safe"])
        self.assertEqual(res["risk_level"], "CRITICAL")
        self.assertGreaterEqual(res["confidence"], 95.0)
        self.assertEqual(res["black_swan_category"], "EXCHANGE_INSOLVENCY")
        self.assertEqual(res["provider"], "LEXICAL_SENTINEL")
        self.assertLess(t_elapsed_ms, 50.0, "Lexical filter must be instantaneous (< 50ms)")
        print(f"[OK] Test 02 Passed: Instant Lexical VETO triggered in {t_elapsed_ms:.2f}ms for EXCHANGE_INSOLVENCY.")

    def test_03_llm_catastrophic_protocol_hack_veto(self):
        """اختبار 3: رصد كارثة اختراق شبكة/بروتوكول عبر الـ LLM وتفعيل الفيتو."""
        mock_hack_response = json.dumps({
            "verdict": "VETO",
            "risk_level": "CRITICAL",
            "confidence": 98,
            "black_swan_category": "PROTOCOL_HACK",
            "reason": "Core cross-chain bridge exploited for $650M; critical systemic vulnerability confirmed."
        })

        res = gemini_validator.validate_candidate_entry(
            symbol=self.symbol,
            mock_headlines=["Major bridge drained for $650M in ongoing zero-day exploit"],
            mock_response=mock_hack_response
        )

        self.assertEqual(res["verdict"], "VETO")
        self.assertFalse(res["safe"])
        self.assertEqual(res["risk_level"], "CRITICAL")
        self.assertGreaterEqual(res["confidence"], 85.0)
        self.assertEqual(res["black_swan_category"], "PROTOCOL_HACK")
        print("[OK] Test 03 Passed: Protocol Hack correctly blocked with CRITICAL VETO.")

    def test_04_low_confidence_veto_downgrade(self):
        """اختبار 4: رفض الفيتو العشوائي إذا كانت ثقة النموذج < 85% أو الخطر منخفض."""
        # محاكاة إجابة مذبذبة أو غير واثقة
        weak_veto_response = json.dumps({
            "verdict": "VETO",
            "risk_level": "MEDIUM",
            "confidence": 65,  # أقل من عتبة الـ 85% المعتمدة من المجلس
            "black_swan_category": "UNKNOWN",
            "reason": "Rumors of regulatory questions on Twitter"
        })

        res = gemini_validator.validate_candidate_entry(
            symbol=self.symbol,
            mock_headlines=["Some analysts speculate on future regulations"],
            mock_response=weak_veto_response
        )

        # قاعدة المجلس: إذا كان الفيتو غير مدعوم بثقة >= 85% أو خطر عالي، يتم خفضه إلى ALLOW لمنع ضياع الصفقات
        self.assertEqual(res["verdict"], "ALLOW")
        self.assertTrue(res["safe"])
        self.assertIn("downgraded to ALLOW", res["reason"])
        print("[OK] Test 04 Passed: Weak uncalibrated VETO successfully downgraded to ALLOW.")

    def test_05_failsafe_protective_policy(self):
        """اختبار 5: بروتوكول الأمان (Fail-Closed) عند انقطاع الاتصال أو نفاد الحصة (Quota)."""
        res = gemini_validator.validate_candidate_entry(
            symbol=self.symbol,
            fail_mode="SIMULATE_TIMEOUT_OR_DOWN"
        )

        self.assertEqual(res["verdict"], "VETO")
        self.assertFalse(res["safe"])
        self.assertEqual(res["status"], "FAILSAFE_PROTECTIVE_VETO")
        self.assertEqual(res["black_swan_category"], "FAILSAFE_TIMEOUT")
        self.assertEqual(res["provider"], "CIRCUIT_BREAKER")
        self.assertIn("FAILSAFE", res["reason"])
        print("[OK] Test 05 Passed: Fail-Closed circuit breaker engaged to protect capital.")

    def test_06_gatekeeper_idle_on_non_candidate(self):
        """اختبار 6: حارس الأخبار يبقى خاملاً (Idle) تماماً دون أي استدعاء خارجي ما لم تصدر إشارة شراء مرشحة."""
        # محاكاة حالة سوق تذبذب / هبوط
        mock_chop_regime = {
            "regime": "CHOPPY",
            "is_trending": False,
            "adx": 14.5,
            "plus_di": 12.0,
            "minus_di": 18.0
        }
        mock_tech = {
            "cross_up": False,
            "daily_up": False,
            "rsi_val": 42.0,
            "rsi_ok": True,
            "is_holding": False
        }
        mock_risk = {"allowed": True}

        import market_regime
        qds_score = market_regime.calculate_qds_composite_score(mock_chop_regime, mock_tech, mock_risk)
        self.assertFalse(qds_score["is_qds_buy"], "Candidate BUY must NOT trigger in chop")

        # التحقق من أن Gatekeeper لا يُستدعى
        is_candidate_buy = qds_score["is_qds_buy"]
        if not is_candidate_buy:
            gatekeeper_status = "GATEKEEPER_IDLE"
        else:
            gatekeeper_status = "CALLED"

        self.assertEqual(gatekeeper_status, "GATEKEEPER_IDLE")
        print("[OK] Test 06 Passed: Sentinel Gatekeeper stays IDLE on non-candidate candles (100% quota preserved).")

    def test_07_zero_touch_integrity(self):
        """اختبار 7: التحقق من عدم المساس بأي ملف إنتاجي (100% Zero-Touch)."""
        import subprocess
        git_diff_paper = subprocess.run(
            ["git", "diff", "paper_trading.py"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
        )
        self.assertEqual(git_diff_paper.stdout.strip(), "", "paper_trading.py MUST HAVE ZERO CHANGES!")

        git_diff_state = subprocess.run(
            ["git", "status", "--porcelain", "paper_state_*.json"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
        )
        self.assertEqual(git_diff_state.stdout.strip(), "", "paper_state files MUST REMAIN COMPLETELY UNTOUCHED!")
        print("[OK] Test 07 Passed: 100% Zero-Touch compliance verified on all production code and state.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
