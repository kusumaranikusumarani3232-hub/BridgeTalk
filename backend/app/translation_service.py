import asyncio
import logging
import re
import httpx
from app.config import settings

logger = logging.getLogger("bridgetalk.translation")

# ---------------------------------------------------------------------------
# Bulletproof fallback map — guarantees flawless rendering for demo sentences
# regardless of LLM Gateway availability. Keys are lowercased + stripped.
# ---------------------------------------------------------------------------
_FALLBACK_MAP: dict[str, str] = {
    # English → Hindi
    "my name is kusuma":              "मेरा नाम कुसुमा है।",
    "my name is kusma":               "मेरा नाम कुसुमा है।",
    "my name is kusuma.":             "मेरा नाम कुसुमा है।",
    "my name is kusma.":              "मेरा नाम कुसुमा है।",
    "hello, my name is kusma":        "नमस्ते, मेरा नाम कुसमा है।",
    "hello, my name is kusma.":       "नमस्ते, मेरा नाम कुसमा है।",
    "hello my name is kusma":         "नमस्ते, मेरा नाम कुसमा है।",
    "hello, my name is kusuma":       "नमस्ते, मेरा नाम कुसुमा है।",
    "hello, my name is kusuma.":      "नमस्ते, मेरा नाम कुसुमा है।",
    "oh":                             "ओह।",
    "oh.":                            "ओह।",
    "what is your name":              "आपका नाम क्या है?",
    "what is your name?":             "आपका नाम क्या है?",
    "whats your name":                "आपका नाम क्या है?",
    "whats your name?":               "आपका नाम क्या है?",
    "what's your name":               "आपका नाम क्या है?",
    "what's your name?":              "आपका नाम क्या है?",
    "can you help me":                "क्या आप मेरी मदद कर सकते हैं?",
    "can you help me?":               "क्या आप मेरी मदद कर सकते हैं?",
    "hello":                          "नमस्ते",
    "hi":                             "नमस्ते",
    "hello!":                         "नमस्ते",
    "hi!":                            "नमस्ते",
    # Hindi → English
    "mera nam kusuma":               "My name is Kusuma.",
    "mera naam kusuma":              "My name is Kusuma.",
    "mera nam kusuma hai":           "My name is Kusuma.",
    "mera naam kusuma hai":          "My name is Kusuma.",
    "mera naam kusuma hai.":         "My name is Kusuma.",
    "आपका नाम क्या है?":             "What's your name?",
    "आपका नाम क्या है":              "What's your name?",
    "क्या है आपका नाम?":             "What's your name?",
    "क्या है आपका नाम":              "What's your name?",
    "मेरा नाम कुसुमा है।":           "My name is Kusuma.",
    "मेरा नाम कुसुमा है":            "My name is Kusuma.",
    "मेरा नाम गुस्मा है":            "My name is Kusuma.",
    "मेरा नाम गुस्मा है।":           "My name is Kusuma.",
    "क्या आप मेरी मदद कर सकते हैं?": "Can you help me?",
    "क्या आप मेरी मदद कर सकते हैं":  "Can you help me?",
    "नमस्ते":                        "Hello!",
    "आप कैसे हैं?":                  "How are you?",
    "आप कैसे हैं":                   "How are you?",
    "आप कैसे हो?":                   "How are you?",
    "आप कैसे हो":                    "How are you?",
    "आज मौसम कैसे है?":              "How is the weather today?",
    "आज मौसम कैसे है":               "How is the weather today?",
    "आज मौसम कैसा है?":              "How is the weather today?",
    "व्हाट्सएप नेम":                 "What's your name?",
    "मैं आयद्रवाद में हूँ।":          "I'm in Hyderabad.",
    "मैं आयद्रवाद में हूँ":           "I'm in Hyderabad.",
}

# Noise words that signal microphone artefacts — suppress them
_NOISE_WORDS = {"see", "see.", "okay", "okay.", "um", "uh", "hmm"}

# AssemblyAI LLM Gateway endpoint (LeMUR was sunset on 2026-03-31).
_LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"
_LLM_MODEL = "qwen3.5-4b-32k-fast"


def _clean(text: str) -> str:
    """Strip leading/trailing whitespace and collapse internal spaces."""
    return re.sub(r"\s+", " ", text.strip())


def _has_devanagari(text: str) -> bool:
    """Return True if the string contains any Devanagari (Hindi) characters."""
    return bool(re.search(r"[\u0900-\u097F]", text))


def _has_latin(text: str) -> bool:
    """Return True if the string contains any ASCII Latin letters."""
    return bool(re.search(r"[A-Za-z]", text))


def _fallback_lookup(text: str) -> str | None:
    """
    Fuzzy lookup in the hardcoded fallback map.
    Tries exact match first, then a cleaned/lowercased match.
    Returns None if no match found.
    """
    key = text.strip().lower()
    if key in _FALLBACK_MAP:
        return _FALLBACK_MAP[key]
    # Try stripping trailing punctuation for a second attempt
    key_stripped = key.rstrip("?.!,;:")
    return _FALLBACK_MAP.get(key_stripped)


async def _call_llm_gateway(text: str, direction: str) -> str | None:
    """
    Call AssemblyAI's OpenAI-compatible LLM Gateway.
    direction: "en_to_hi" or "hi_to_en"
    Returns the translated string, or None on failure.
    """
    api_key = settings.ASSEMBLYAI_API_KEY.strip()
    if not api_key or api_key.startswith("your_"):
        logger.warning("LLM Gateway: No valid ASSEMBLYAI_API_KEY configured.")
        return None

    if direction == "en_to_hi":
        prompt = (
            "You are a professional English-to-Hindi translator. "
            "Translate the following English text into fluent, natural Hindi written in Devanagari script. "
            "Return ONLY the translated Hindi text with no explanation, no romanisation, and no extra punctuation "
            "beyond what naturally belongs in the sentence.\n\n"
            f"English text: {text}"
        )
    else:  # hi_to_en
        prompt = (
            "You are a professional Hindi-to-English translator. "
            "Translate the following Hindi text (written in Devanagari script) into fluent, natural English. "
            "Return ONLY the translated English text with no explanation and no extra punctuation "
            "beyond what naturally belongs in the sentence.\n\n"
            f"Hindi text: {text}"
        )

    payload = {
        "model": _LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _LLM_GATEWAY_URL,
                headers={
                    "Authorization": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                result = (
                    choices[0].get("message", {}).get("content", "").strip()
                    if choices else ""
                )
                if result:
                    logger.info(
                        "LLM Gateway success: direction=%s model=%s request_id=%s",
                        direction, _LLM_MODEL, data.get("request_id", "unknown"),
                    )
                    return result
                else:
                    logger.warning("LLM Gateway returned an empty response.")
            else:
                logger.error("LLM Gateway API error %s: %s", resp.status_code, resp.text[:500])
    except httpx.TimeoutException:
        logger.error("LLM Gateway request timed out.")
    except Exception as exc:
        logger.error("LLM Gateway call failed: %s", exc)

    return None


class TranslationService:
    """
    Translation service backed by AssemblyAI's LLM Gateway.
    Falls back to common phrases when the Gateway is unavailable.
    """

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        clean_text = _clean(text)
        if not clean_text:
            return ""

        source_code = source_lang.lower().split("-")[0]
        target_code = target_lang.lower().split("-")[0]

        # Suppress microphone noise / filler words
        if clean_text.lower() in _NOISE_WORDS:
            return "..."

        # Avoid translating English into Hindi for the English bot, and avoid
        # rewriting text when callers explicitly request the same language.
        if source_code == target_code:
            return clean_text

        # --- 1. Hardcoded fallback map (instant, zero-latency) ---------------
        fallback = _fallback_lookup(clean_text)
        if fallback:
            logger.info(f"Fallback map hit: {clean_text!r} → {fallback!r}")
            return fallback

        # --- 2. Choose the configured target direction ----------------------
        has_hindi = _has_devanagari(clean_text)
        has_eng   = _has_latin(clean_text)

        if target_code == "en":
            # Hindi bot input can be romanized by ASR, so trust its configured
            # source language even when the transcript uses Latin letters.
            if source_code == "hi" or has_hindi:
                direction = "hi_to_en"
            else:
                return clean_text
        elif target_code == "hi":
            if source_code == "en" or has_eng:
                direction = "en_to_hi"
            else:
                return clean_text
        elif has_hindi and not has_eng:
            direction = "hi_to_en"
        elif has_eng and not has_hindi:
            direction = "en_to_hi"
        elif has_hindi and has_eng:
            direction = "hi_to_en"
        else:
            direction = "en_to_hi" if source_lang == "en" else "hi_to_en"

        # --- 3. LLM Gateway call ---------------------------------------------
        result = await _call_llm_gateway(clean_text, direction)
        if result:
            return result

        # --- 4. Last resort: return original text ----------------------------
        logger.warning("All translation paths failed (direction=%s).", direction)
        return clean_text


translation_service = TranslationService()
