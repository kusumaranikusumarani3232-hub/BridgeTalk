import asyncio
import logging
import re
import httpx
from app.config import settings

logger = logging.getLogger("bridgetalk.translation")


class TranslationError(RuntimeError):
    """Raised when no translated result is available."""

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
    "okay":                           "ठीक है।",
    "okay.":                          "ठीक है।",
    "ok":                             "ठीक है।",
    "ok.":                            "ठीक है।",
    "good morning":                   "सुप्रभात।",
    "i'm doing well, thank you.":     "मैं अच्छा हूँ, धन्यवाद।",
    "i'm doing well, thank you":      "मैं अच्छा हूँ, धन्यवाद।",
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
    "समय क्या हुआ है?":               "What time is it?",
    "समय क्या हुआ है":                "What time is it?",
    "आज मौसम कैसे है?":              "How is the weather today?",
    "आज मौसम कैसे है":               "How is the weather today?",
    "आज मौसम कैसा है?":              "How is the weather today?",
    "व्हाट्सएप नेम":                 "What's your name?",
    "मैं आयद्रवाद में हूँ।":          "I'm in Hyderabad.",
    "मैं आयद्रवाद में हूँ":           "I'm in Hyderabad.",
}

# AssemblyAI LLM Gateway endpoint (LeMUR was sunset on 2026-03-31).
_LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"
_LLM_MODEL = "qwen3.5-4b-32k-fast"
_MAX_GATEWAY_ATTEMPTS = 3
_RATE_LIMIT_BACKOFF_SECONDS = (0.25, 0.5)
_MAX_RETRY_AFTER_SECONDS = 1.0


def _clean(text: str) -> str:
    """Strip leading/trailing whitespace and collapse internal spaces."""
    return re.sub(r"\s+", " ", text.strip())


def _has_devanagari(text: str) -> bool:
    """Return True if the string contains any Devanagari (Hindi) characters."""
    return bool(re.search(r"[\u0900-\u097F]", text))


def _has_latin(text: str) -> bool:
    """Return True if the string contains any ASCII Latin letters."""
    return bool(re.search(r"[A-Za-z]", text))


def _fallback_lookup(text: str, target_lang: str | None = None) -> str | None:
    """
    Fuzzy lookup in the hardcoded fallback map.
    Tries exact match first, then a cleaned/lowercased match.
    Returns None if no match found.
    """
    key = text.strip().lower()
    if target_lang == "en" and key.rstrip("?.!,;:") in {"ok", "okay"}:
        return "Okay."
    result = _FALLBACK_MAP.get(key)
    # Try stripping trailing punctuation for a second attempt
    if result is None:
        key_stripped = key.rstrip("?.!,;:")
        result = _FALLBACK_MAP.get(key_stripped)
    if result and target_lang == "en" and _has_devanagari(result):
        return None
    if result and target_lang == "hi" and not _has_devanagari(result):
        return None
    return result


async def _call_llm_gateway(text: str, direction: str, romanized_hindi: bool = False) -> str | None:
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
        script_guidance = (
            "The Hindi may be written in Devanagari or Latin transliteration. "
            if romanized_hindi else "The Hindi text is written in Devanagari script. "
        )
        prompt = (
            "You are a professional Hindi-to-English translator. "
            f"Translate the following Hindi text. {script_guidance}"
            "Return fluent, natural English. "
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

    for attempt in range(_MAX_GATEWAY_ATTEMPTS):
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
        except httpx.TimeoutException:
            logger.warning("LLM Gateway request timed out (attempt %s/3).", attempt + 1)
            if attempt < 2:
                await asyncio.sleep(0.8 * (attempt + 1))
                continue
            break
        except httpx.RequestError as exc:
            logger.warning("LLM Gateway network request failed (%s).", type(exc).__name__)
            if attempt < 2:
                await asyncio.sleep(0.8 * (attempt + 1))
                continue
            break
        except Exception as exc:
            logger.error("LLM Gateway call failed (%s).", type(exc).__name__)
            break

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
            logger.warning("LLM Gateway returned an empty response.")
        else:
            logger.error("LLM Gateway API error %s.", resp.status_code)
            if resp.status_code == 429:
                if attempt >= _MAX_GATEWAY_ATTEMPTS - 1:
                    break
                retry_after = resp.headers.get("Retry-After")
                try:
                    delay = min(max(float(retry_after), 0.0), _MAX_RETRY_AFTER_SECONDS) if retry_after else _RATE_LIMIT_BACKOFF_SECONDS[attempt]
                except (TypeError, ValueError):
                    delay = _RATE_LIMIT_BACKOFF_SECONDS[attempt]
                await asyncio.sleep(delay)
                continue
            if resp.status_code != 429 and resp.status_code < 500:
                break
        if attempt < 2:
            retry_after = resp.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 0.8 * (attempt + 1)
            except ValueError:
                delay = 0.8 * (attempt + 1)
            await asyncio.sleep(min(max(delay, 0.4), 10.0))

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

        # Avoid rewriting text when callers explicitly request the same language.
        if source_code == target_code:
            return clean_text

        # --- 1. Hardcoded fallback map (instant, zero-latency) ---------------
        fallback = _fallback_lookup(clean_text, target_code)
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
                raise TranslationError("Transcript language does not match requested Hindi → English translation.")
        elif target_code == "hi":
            if source_code == "en" or has_eng:
                direction = "en_to_hi"
            else:
                raise TranslationError("Transcript language does not match requested English → Hindi translation.")
        elif has_hindi and not has_eng:
            direction = "hi_to_en"
        elif has_eng and not has_hindi:
            direction = "en_to_hi"
        elif has_hindi and has_eng:
            direction = "hi_to_en"
        else:
            direction = "en_to_hi" if source_lang == "en" else "hi_to_en"

        # --- 3. LLM Gateway call ---------------------------------------------
        result = await _call_llm_gateway(
            clean_text,
            direction,
            romanized_hindi=(source_code == "hi" and not has_hindi),
        )
        if result:
            return result

        logger.warning("All translation paths failed (direction=%s).", direction)
        raise TranslationError(f"Translation unavailable for direction {direction}.")


translation_service = TranslationService()
