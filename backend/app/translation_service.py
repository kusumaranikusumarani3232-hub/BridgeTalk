import asyncio
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import httpx
from app.config import settings

logger = logging.getLogger("bridgetalk.translation")


class TranslationError(RuntimeError):
    """Raised when no translated result is available."""

# AssemblyAI LLM Gateway endpoint (LeMUR was sunset on 2026-03-31).
_LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"
_LLM_MODEL = "qwen3.5-4b-32k-fast"
_MAX_GATEWAY_ATTEMPTS = 3
_MAX_RETRY_AFTER_SECONDS = 5.0
_MIN_GATEWAY_REQUEST_INTERVAL = 0.25
_gateway_cooldown_until = 0.0
_gateway_next_request_at = 0.0
_gateway_lock = asyncio.Lock()


def _rate_limit_cooldown(resp) -> float:
    """Bound server-provided cooldowns; fall back to a short local cooldown."""
    retry_after = resp.headers.get("Retry-After")
    try:
        if not retry_after:
            return 1.0
        try:
            seconds = float(retry_after)
        except ValueError:
            retry_at = parsedate_to_datetime(retry_after)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
        return min(max(seconds, 0.25), _MAX_RETRY_AFTER_SECONDS)
    except (TypeError, ValueError):
        return 1.0


def _clean(text: str) -> str:
    """Strip leading/trailing whitespace and collapse internal spaces."""
    return re.sub(r"\s+", " ", text.strip())


def _has_devanagari(text: str) -> bool:
    """Return True if the string contains any Devanagari (Hindi) characters."""
    return bool(re.search(r"[\u0900-\u097F]", text))


def _has_latin(text: str) -> bool:
    """Return True if the string contains any ASCII Latin letters."""
    return bool(re.search(r"[A-Za-z]", text))


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

    global _gateway_cooldown_until, _gateway_next_request_at
    async with _gateway_lock:
        # Hold the shared lock while waiting so queued requests recover in
        # order and never hit the gateway concurrently after a 429.
        cooldown_wait = _gateway_cooldown_until - asyncio.get_running_loop().time()
        if cooldown_wait > 0:
            await asyncio.sleep(cooldown_wait)
        for attempt in range(_MAX_GATEWAY_ATTEMPTS):
            spacing = _gateway_next_request_at - asyncio.get_running_loop().time()
            if spacing > 0:
                await asyncio.sleep(spacing)
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        _LLM_GATEWAY_URL,
                        headers={"Authorization": api_key, "Content-Type": "application/json"},
                        json=payload,
                    )
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.warning("LLM Gateway request failed (%s).", type(exc).__name__)
                if attempt < _MAX_GATEWAY_ATTEMPTS - 1:
                    await asyncio.sleep(0.8 * (attempt + 1))
                    continue
                return None
            except Exception as exc:
                logger.error("LLM Gateway call failed (%s).", type(exc).__name__)
                return None

            completed_at = asyncio.get_running_loop().time()
            _gateway_next_request_at = completed_at + _MIN_GATEWAY_REQUEST_INTERVAL
            if resp.status_code == 429:
                cooldown = _rate_limit_cooldown(resp)
                _gateway_cooldown_until = completed_at + cooldown
                logger.warning("LLM Gateway rate limited; cooldown %.2fs.", cooldown)
                return None
            if resp.status_code == 200:
                _gateway_cooldown_until = 0.0
                try:
                    data = resp.json()
                    choices = data.get("choices") or []
                    result = choices[0].get("message", {}).get("content", "").strip() if choices else ""
                except Exception as exc:
                    logger.warning("LLM Gateway returned invalid response (%s).", type(exc).__name__)
                    return None
                if result:
                    logger.info(
                        "LLM Gateway success: direction=%s model=%s request_id=%s",
                        direction, _LLM_MODEL, data.get("request_id", "unknown"),
                    )
                    return result
                logger.warning("LLM Gateway returned an empty response.")
                return None

            logger.error("LLM Gateway API error %s.", resp.status_code)
            if resp.status_code < 500 or attempt == _MAX_GATEWAY_ATTEMPTS - 1:
                return None
            await asyncio.sleep(0.8 * (attempt + 1))

    return None


class TranslationService:
    """
    Translation service backed by AssemblyAI's LLM Gateway.
    Returns only real gateway translations; failures are surfaced to the turn.
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

        # --- Choose the configured target direction --------------------------
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

        # --- LLM Gateway call -------------------------------------------------
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
