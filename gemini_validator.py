"""
======================================================================
 🤖 GEMINI RESPONSE VALIDATOR — وحدة تدقيق وفحص مخرجات الذكاء الاصطناعي
======================================================================
تفحص وتحلل ردود Gemini المتغيرة وتضمن أنها ضمن النطاقات المسموحة،
مع تسجيل صريح لحالات الفشل (API_ERROR, TIMEOUT, INVALID_RESPONSE).
"""
import json
import logging

def parse_and_validate_gemini_response(raw_response: str) -> dict:
    """
    تدقيق وتطهير رد Gemini وتأكيد نطاق القيم الهيكلية.
    إرجاع dict دقيق يحتوي على البيانات ومؤشر الحالة.
    """
    default_result = {
        "status": "NEUTRAL_FALLBACK",
        "sentiment_score": 0.0,
        "impact": "LOW",
        "confidence": 0.0,
        "event_type": "UNKNOWN",
        "direction": "NEUTRAL",
        "novelty": 0.5,
        "source_quality": "UNKNOWN",
        "shock_detected": False,
        "safe": True,
        "reason": "Safe fallback applied"
    }

    if not raw_response or not isinstance(raw_response, str):
        default_result["status"] = "EMPTY_OR_TIMEOUT"
        default_result["reason"] = "Gemini return was empty or timed out"
        return default_result

    try:
        clean_text = raw_response.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_text)
        
        if not isinstance(data, dict):
            default_result["status"] = "INVALID_RESPONSE_FORMAT"
            default_result["reason"] = "Gemini output was not a JSON object"
            return default_result

        # 1. Sentiment Score (-1.0 to +1.0)
        sent = float(data.get('sentiment_score', 0.0))
        sent = max(-1.0, min(1.0, sent))
        
        # 2. Confidence (0.0 to 100.0 or 0.0 to 1.0)
        conf = float(data.get('confidence', 50.0))
        if conf > 1.0: conf = conf / 100.0
        conf = max(0.0, min(1.0, conf))

        # 3. Safe Boolean
        safe = bool(data.get('safe', True))
        shock = bool(data.get('shock_detected', False))
        
        return {
            "status": "VALID",
            "sentiment_score": round(sent, 2),
            "impact": str(data.get('impact', 'MEDIUM')).upper(),
            "confidence": round(conf, 2),
            "event_type": str(data.get('event_type', 'GENERAL')),
            "direction": str(data.get('direction', 'NEUTRAL')).upper(),
            "novelty": round(float(data.get('novelty', 0.5)), 2),
            "source_quality": str(data.get('source_quality', 'STANDARD')),
            "shock_detected": shock,
            "safe": safe and not shock,
            "reason": str(data.get('reason', 'تم فحص الرد وتدقيقه بنجاح'))
        }

    except json.JSONDecodeError:
        default_result["status"] = "INVALID_JSON_SYNTAX"
        default_result["reason"] = "فشل في فك شفرة الـ JSON الصادر من Gemini"
        return default_result
    except Exception as e:
        default_result["status"] = "PARSE_ERROR"
        default_result["reason"] = f"خطأ تدقيق استجابة Gemini: {e}"
        return default_result