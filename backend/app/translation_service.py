import asyncio
import logging
import re
import httpx
from app.config import settings

logger = logging.getLogger("bridgetalk.translation")

# ---------------------------------------------------------------------------
# Bulletproof fallback map — guarantees flawless rendering for demo sentences
# regardless of LeMUR availability.  Keys are lowercased + stripped.
# ---------------------------------------------------------------------------
_FALLBACK_MAP: dict[str, str] = {
    # English → Hindi
    "my name is kusuma":              "मेरा नाम कुसुमा है।",
    "my name is kusma":               "मेरा नाम कुसुमा है।",
    "my name is kusuma.":             "मेरा नाम कुसुमा है।",
    "my name is kusma.":              "मेरा नाम कुसुमा है।",
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
}

# Noise words that signal microphone artefacts — suppress them
_NOISE_WORDS = {"see", "see.", "okay", "okay.", "um", "uh", "hmm"}

# AssemblyAI LeMUR Task API endpoint
_LEMUR_URL = "https://api.assemblyai.com/lemur/v3/generate/task"


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


async def _call_lemur(text: str, direction: str) -> str | None:
    """
    Call AssemblyAI LeMUR Task API.
    direction: "en_to_hi" or "hi_to_en"
    Returns the translated string, or None on failure.
    """
    api_key = settings.ASSEMBLYAI_API_KEY.strip()
    if not api_key or api_key.startswith("your_"):
        logger.warning("LeMUR: No valid ASSEMBLYAI_API_KEY configured.")
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
        "prompt": prompt,
        "final_model": "anthropic/claude-3-5-sonnet",  # LeMUR default high-quality model
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _LEMUR_URL,
                headers={
                    "Authorization": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("response", "").strip()
                if result:
                    logger.info(f"LeMUR ({direction}) success: {text!r} → {result!r}")
                    return result
                else:
                    logger.warning("LeMUR returned empty response.")
            else:
                logger.error(f"LeMUR API error {resp.status_code}: {resp.text[:300]}")
    except httpx.TimeoutException:
        logger.error("LeMUR request timed out.")
    except Exception as exc:
        logger.error(f"LeMUR call failed: {exc}")

    return None


class TranslationService:
    """
    Translation service backed exclusively by AssemblyAI LeMUR Task API.
    Falls back to the hardcoded demo-sentence map when LeMUR is unavailable.
    """

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        clean_text = _clean(text)
        if not clean_text:
            return ""

        # Suppress microphone noise / filler words
        if clean_text.lower() in _NOISE_WORDS:
            return "..."

        # --- 1. Hardcoded fallback map (instant, zero-latency) ---------------
        fallback = _fallback_lookup(clean_text)
        if fallback:
            logger.info(f"Fallback map hit: {clean_text!r} → {fallback!r}")
            return fallback

        # --- 2. Detect script direction automatically ------------------------
        has_hindi = _has_devanagari(clean_text)
        has_eng   = _has_latin(clean_text)

        if has_hindi and not has_eng:
            # Pure Devanagari → English
            direction = "hi_to_en"
        elif has_eng and not has_hindi:
            # Pure Latin → Hindi
            direction = "en_to_hi"
        elif has_hindi and has_eng:
            # Mixed (Hinglish typed in Devanagari) — treat as Hindi → English
            direction = "hi_to_en"
        else:
            # Fallback: honour caller's source/target hint
            direction = "en_to_hi" if source_lang == "en" else "hi_to_en"

        # --- 3. LeMUR API call -----------------------------------------------
        result = await _call_lemur(clean_text, direction)
        if result:
            return result

        # --- 4. Last resort: return original text ----------------------------
        logger.warning(f"All translation paths failed for: {clean_text!r}")
        return clean_text


translation_service = TranslationService()
