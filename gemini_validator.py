"""
=============================================================================
🤖 GEMINI NEWS SENTINEL (PHASE 4) — حارس الأخبار والمشاعر الذكي
=============================================================================
تم تصميمه واعتماده بموجب ميثاق ومناظرة مجلس الذكاء الاصطناعي (AI Council):
1. دور النموذج (LLM Scope): حظر تام لأي تحليل فني، ينحصر الدور حصراً في
   كشف الكوارث والأحداث الكبرى (Black Swan, Protocol Hacks, Exchange Insolvency, Regulatory Bans).
2. ترشيد الاستدعاء (Gatekeeper Only): لا يُستدعى إلا عند صدور إشارة شراء مرشحة (Candidate BUY)
   بدرجة مركبة QDS >= 80، لتوفير استهلاك الـ API بنسبة > 85%.
3. سياسة الفشل الآمن (Fail-Closed Protective Protocol): عند انقطاع الاتصال أو نفاد
   الحصة أو بطء الاستجابة (> 5 ثوانٍ)، يفشل النظام بالإغلاق الحمائي (VETO) لحماية رأس المال.
4. هندسة المناعة والاحتياط (Multi-Provider Fallback):
   - المصدر الأساسي: Google Gemini API (gemini-3.8-flash / gemini-flash-latest).
   - المصدر الاحتياطي الفوري: Groq API (openai/gpt-oss-120b).
   - الفلتر الحتمي الفوري: محرك فحص الكلمات المفتاحية الكارثية دون أي كمون شبكي.
=============================================================================
"""

import os
import sys
import json
import time
import logging
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

# إعداد السجل
logger = logging.getLogger("GeminiSentinel")

# مسارات المفاتيح المحفوظة محلياً على جهاز المستخدم
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
GEMINI_KEY_FILE = os.path.join(DESKTOP, "googleAPI.txt")
GROQ_KEY_FILE = os.path.join(DESKTOP, "API.txt")

# الكلمات المفتاحية الكارثية (Black Swan Deterministic Lexicon)
BLACK_SWAN_LEXICON = {
    "EXCHANGE_INSOLVENCY": [
        "pause withdrawal", "pauses withdrawal", "paused withdrawal", "halting withdrawal",
        "halts withdrawal", "halted withdrawal", "frozen funds", "freeze asset",
        "chapter 11", "insolvency", "insolvent", "bank run", "liquidity crisis",
        "bankruptcy filing", "cease operation"
    ],
    "PROTOCOL_HACK": [
        "51% attack", "bridge drained", "private key stolen", "smart contract exploit",
        "reentrancy attack", "multisig compromised", "infinite mint", "hacked for $"
    ],
    "REGULATORY_BAN": [
        "emergency ban", "criminal indictment", "doj raid", "nationwide ban",
        "subpoena tier-1", "arrest warrant", "sec emergency order"
    ],
    "NETWORK_HALT": [
        "chain halted", "validators stop", "consensus failure", "deep reorg", "hard fork split"
    ]
}

def load_key_from_file(filepath: str, prefix: str = None) -> str:
    """قراءة المفتاح المخزن محلياً بأمان."""
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                if prefix:
                    for line in lines:
                        if line.startswith(prefix):
                            return line
                return lines[0] if lines else ""
    except Exception as e:
        logger.warning(f"⚠️ تعذر قراءة المفتاح من {filepath}: {e}")
    return ""

def get_gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY") or load_key_from_file(GEMINI_KEY_FILE)

def get_groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY") or load_key_from_file(GROQ_KEY_FILE, "gsk_")

def fetch_breaking_crypto_headlines(limit: int = 15, timeout: int = 4) -> list:
    """جلب العناوين الإخبارية الحية العاجلة للبيتكوين والعملات المشفرة عبر RSS."""
    rss_url = "https://news.google.com/rss/search?q=Bitcoin+crypto+when:12h&hl=en-US&gl=US&ceid=US:en"
    headlines = []
    try:
        req = urllib.request.Request(
            rss_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml_data = resp.read().decode("utf-8", errors="replace")
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")
            for item in items[:limit]:
                t_el = item.find("title")
                if t_el is not None and t_el.text:
                    clean_title = t_el.text.strip()
                    # إزالة اسم المصدر المرفق في نهاية العنوان (مثل - Coindesk)
                    if " - " in clean_title:
                        clean_title = clean_title.rsplit(" - ", 1)[0].strip()
                    headlines.append(clean_title)
    except Exception as e:
        logger.warning(f"⚠️ تعذر جلب الأخبار الحية عبر RSS ({e})")
    return headlines

def detect_black_swan_keywords(headlines: list) -> tuple:
    """
    محرك فحص الكلمات المفتاحية الحتمي (Deterministic Fast Filter).
    يرصد أي كارثة مؤكدة فورياً دون كمون شبكي.
    يعيد: (is_critical, category, matched_text)
    """
    for h in headlines:
        h_lower = h.lower()
        for cat, keywords in BLACK_SWAN_LEXICON.items():
            for kw in keywords:
                if kw in h_lower:
                    return True, cat, h
    return False, "NONE", ""

def query_gemini_api(prompt: str, api_key: str, timeout: float = 2.5) -> str:
    """استدعاء Gemini API عبر الموديل الأحدث."""
    models_to_try = ["gemini-3.8-flash", "gemini-flash-latest"]
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.0
        }
    }).encode("utf-8")

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.warning(f"⚠️ فشل استدعاء Gemini ({model}): {e}")
            # إذا كان الخطأ 503 أو 429 لا داعي لتكرار المحاولة مع موديل آخر من نفس المزود
            if "503" in str(e) or "429" in str(e):
                break
    return None

def query_groq_fallback(prompt: str, api_key: str, timeout: int = 5) -> str:
    """استدعاء Groq API كمصدر ذكاء احتياطي فوري."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = json.dumps({
        "model": "openai/gpt-oss-120b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the Emergency News Sentinel for an automated BTC trading desk. "
                    "Respond STRICTLY in valid JSON matching the exact schema."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"⚠️ فشل استدعاء Groq الاحتياطي: {e}")
    return None

def parse_and_validate_gemini_response(raw_response: str) -> dict:
    """
    تدقيق وتطهير رد الذكاء الاصطناعي وتأكيد المخطط الصارم المعتمد من المجلس.
    """
    default_result = {
        "status": "PARSE_ERROR",
        "verdict": "VETO",
        "risk_level": "HIGH",
        "confidence": 0.0,
        "black_swan_category": "UNKNOWN",
        "safe": False,
        "reason": "Invalid or unparseable response format"
    }

    if not raw_response or not isinstance(raw_response, str):
        default_result["status"] = "EMPTY_RESPONSE"
        default_result["reason"] = "Sentinel return was empty or timed out"
        return default_result

    try:
        clean_text = raw_response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)

        if not isinstance(data, dict):
            default_result["status"] = "NOT_A_DICT"
            return default_result

        verdict = str(data.get("verdict", "VETO")).upper().strip()
        if verdict not in ["ALLOW", "VETO"]:
            verdict = "VETO"

        risk_level = str(data.get("risk_level", "MEDIUM")).upper().strip()
        if risk_level not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            risk_level = "HIGH"

        # ثقة النموذج (0 to 100)
        conf = float(data.get("confidence", 50.0))
        if conf <= 1.0 and conf > 0.0:
            conf = conf * 100.0
        conf = max(0.0, min(100.0, conf))

        category = str(data.get("black_swan_category", "NONE")).upper().strip()
        reason = str(data.get("reason", "تم فحص الأخبار والتحقق من سلامة السوق")).strip()

        # قاعدة الحسم المعتمدة من مجلس الذكاء:
        # VETO معتمد فقط إذا كان الخطر HIGH أو CRITICAL والثقة >= 85%
        is_safe = True
        if verdict == "VETO":
            if risk_level in ["HIGH", "CRITICAL"] and conf >= 85.0:
                is_safe = False
            else:
                # إذا كانت الثقة منخفضة أو الخطر غير كافٍ، لا يُقبل الفيتو العشوائي
                verdict = "ALLOW"
                is_safe = True
                reason += " [VETO downgraded to ALLOW: Confidence < 85% or Risk not critical]"

        return {
            "status": "VALID",
            "verdict": verdict,
            "risk_level": risk_level,
            "confidence": round(conf, 1),
            "black_swan_category": category,
            "safe": is_safe,
            "reason": reason
        }

    except json.JSONDecodeError as jde:
        default_result["status"] = "INVALID_JSON_SYNTAX"
        default_result["reason"] = f"JSON Decode Error: {jde}"
        return default_result
    except Exception as e:
        default_result["status"] = "EXCEPTION"
        default_result["reason"] = f"Validation Exception: {e}"
        return default_result

def build_sentinel_prompt(headlines: list, symbol: str = "BTC/USDT") -> str:
    """بناء موجه الحارس الصارم (System Prompt) المانع للهلوسة."""
    headlines_text = "\n".join(f"- {h}" for h in headlines) if headlines else "- No breaking news reported in the last 12 hours."
    
    return f"""You are the Emergency News Sentinel for an automated {symbol} quantitative trading desk.
Your SOLE AND EXCLUSIVE mission is to detect CATASTROPHIC BLACK SWAN events that could cause instantaneous market collapse.

Permitted Black Swan Categories:
- EXCHANGE_INSOLVENCY: Tier-1 exchange bankruptcies, sudden withdrawal freezes, asset liquidations.
- PROTOCOL_HACK: $100M+ core protocol exploits, major smart contract hacks, consensus breaches.
- REGULATORY_BAN: Nationwide total crypto bans, criminal indictments/arrests of tier-1 founders, emergency DOJ actions.
- NETWORK_HALT: Blockchain halts, validator forks, consensus paralysis.

CRITICAL INSTRUCTIONS:
1. DO NOT perform technical analysis. DO NOT analyze charts, RSI, or price action.
2. DO NOT react to ordinary volatility, routine CPI reports, standard ETF inflows/outflows, or generic market sentiment.
3. If no catastrophic Black Swan event is detected, verdict MUST be ALLOW with risk_level LOW.
4. Output STRICTLY a valid JSON object matching this schema:

{{
  "verdict": "ALLOW" or "VETO",
  "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "confidence": 0-100,
  "black_swan_category": "NONE" | "EXCHANGE_INSOLVENCY" | "PROTOCOL_HACK" | "REGULATORY_BAN" | "NETWORK_HALT",
  "reason": "Clear concise justification"
}}

Current Live Headlines:
{headlines_text}"""

def validate_candidate_entry(symbol: str = "BTC/USDT", technical_meta: dict = None,
                             mock_response: str = None, mock_headlines: list = None,
                             fail_mode: str = None) -> dict:
    """
    بوابة التحقق التنفيذية لحارس الأخبار (Candidate BUY Sentinel Gatekeeper).
    تُستدعى حصراً عند صدور إشارة شراء مرشحة (Candidate BUY) من محرك QDS.
    """
    start_t = time.time()

    # 1. دعم سيناريو الفشل المحاكى للاختبارات
    if fail_mode == "SIMULATE_TIMEOUT_OR_DOWN":
        logger.warning("🚨 [Fail-Closed] محاكاة انقطاع الاتصال وتفعيل الحظر الحمائي.")
        return {
            "status": "FAILSAFE_PROTECTIVE_VETO",
            "verdict": "VETO",
            "risk_level": "HIGH",
            "confidence": 90.0,
            "black_swan_category": "FAILSAFE_TIMEOUT",
            "safe": False,
            "reason": "FAILSAFE: External sentinel unreachable during candidate entry. Blocked to prevent blind trading.",
            "latency_ms": 5000.0,
            "provider": "CIRCUIT_BREAKER"
        }

    # 2. جلب الأخبار الحية
    headlines = mock_headlines if mock_headlines is not None else fetch_breaking_crypto_headlines(limit=12, timeout=4)

    # 3. الفحص الحتمي السريع للكلمات المفتاحية الكارثية
    is_critical_kw, cat_kw, matched_kw = detect_black_swan_keywords(headlines)
    if is_critical_kw:
        logger.critical(f"🚨 [Deterministic VETO] رصد كارثة مؤكدة عبر الكلمات المفتاحية: {matched_kw} ({cat_kw})")
        return {
            "status": "VALID",
            "verdict": "VETO",
            "risk_level": "CRITICAL",
            "confidence": 98.0,
            "black_swan_category": cat_kw,
            "safe": False,
            "reason": f"DETERMINISTIC VETO: Catastrophic keyword detected in breaking headline: '{matched_kw}'",
            "latency_ms": round((time.time() - start_t) * 1000, 2),
            "provider": "LEXICAL_SENTINEL"
        }

    # 4. إذا تم تزويد رد محاكى (Unit Testing)
    if mock_response is not None:
        parsed = parse_and_validate_gemini_response(mock_response)
        parsed["latency_ms"] = round((time.time() - start_t) * 1000, 2)
        parsed["provider"] = "MOCK_SENTINEL"
        return parsed

    # 5. بناء الموجه والاستدعاء المتعدد (Primary -> Secondary -> Fail-Closed)
    prompt = build_sentinel_prompt(headlines, symbol)

    # أ. تجربة Gemini الأساسي
    gemini_key = get_gemini_api_key()
    raw_resp = None
    provider_used = None

    if gemini_key:
        raw_resp = query_gemini_api(prompt, gemini_key, timeout=4)
        if raw_resp:
            provider_used = "GEMINI_PRIMARY"

    # ب. إذا تعذر Gemini، التبديل إلى Groq الاحتياطي الفوري
    if not raw_resp:
        groq_key = get_groq_api_key()
        if groq_key:
            logger.info("🔄 الانتقال إلى مزود الذكاء الاحتياطي (Groq Fallback)...")
            raw_resp = query_groq_fallback(prompt, groq_key, timeout=4)
            if raw_resp:
                provider_used = "GROQ_FALLBACK"

    # ج. إذا نجح أي من النموذجين
    if raw_resp:
        parsed = parse_and_validate_gemini_response(raw_resp)
        parsed["latency_ms"] = round((time.time() - start_t) * 1000, 2)
        parsed["provider"] = provider_used
        return parsed

    # د. في حال تعذر جميع النماذج الخارجية (انقطاع كامل أو نفاد الحصة) -> تطبيق سياسة الفشل بالإغلاق
    logger.warning("🛡️ [Fail-Closed] تعذر الاتصال بجميع مزودي الأخبار. تفعيل الحظر الحمائي للصفقة المرشحة.")
    return {
        "status": "FAILSAFE_PROTECTIVE_VETO",
        "verdict": "VETO",
        "risk_level": "HIGH",
        "confidence": 90.0,
        "black_swan_category": "FAILSAFE_TIMEOUT",
        "safe": False,
        "reason": "FAILSAFE: External sentinel unreachable during candidate entry. Blocked to protect capital from news blackout.",
        "latency_ms": round((time.time() - start_t) * 1000, 2),
        "provider": "CIRCUIT_BREAKER_FAIL_CLOSED"
    }