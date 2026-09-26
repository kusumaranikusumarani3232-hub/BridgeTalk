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

_TRANSLATION_LOCK = asyncio.Lock()
_GROQ_COOLDOWN_UNTIL = 0.0
_GROQ_NEXT_REQUEST_AT = 0.0
_GROQ_MIN_INTERVAL_SECONDS = 2.1
_GROQ_MAX_COOLDOWN_SECONDS = 5.0


def _clean(text: str) -> str:
    """Strip leading/trailing whitespace and collapse internal spaces."""
    return re.sub(r"\s+", " ", text.strip())


def _has_devanagari(text: str) -> bool:
    """Return True if the string contains any Devanagari (Hindi) characters."""
    return bool(re.search(r"[\u0900-\u097F]", text))


def _has_latin(text: str) -> bool:
    """Return True if the string contains any ASCII Latin letters."""
    return bool(re.search(r"[A-Za-z]", text))


async def _call_ollama(text: str, direction: str, romanized_hindi: bool = False) -> str | None:
    """
    Call the locally running Ollama chat API using the existing translation prompts.
    direction: "en_to_hi" or "hi_to_en"
    Returns the translated string, or None on failure.
    """
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [{"role": "user", "content": _translation_prompt(text, direction, romanized_hindi)}],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 512},
    }
    endpoint = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    # The session queue serializes turns per client; this lock also prevents
    # separate client sockets from overloading one local Ollama instance.
    async with _TRANSLATION_LOCK:
        try:
            timeout = httpx.Timeout(180.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            result = (data.get("message") or {}).get("content", "").strip()
            if result:
                logger.info("Ollama translation success: direction=%s model=%s", direction, settings.OLLAMA_MODEL)
                return result
            logger.warning("Ollama returned an empty translation.")
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s; start Ollama and pull %s.", endpoint, settings.OLLAMA_MODEL)
        except httpx.HTTPStatusError as exc:
            logger.error("Ollama API returned HTTP %s: %s", exc.response.status_code, exc.response.text[:500])
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.error("Ollama request failed (%s).", type(exc).__name__)
        except Exception as exc:
            logger.error("Ollama translation failed (%s).", type(exc).__name__)
    return None


def _translation_prompt(text: str, direction: str, romanized_hindi: bool = False) -> str:
    """Keep the existing translation instructions identical across providers."""
    if direction == "en_to_hi":
        return (
            "You are a professional English-to-Hindi translator. "
            "Translate the following English text into fluent, natural Hindi written in Devanagari script. "
            "Return ONLY the translated Hindi text with no explanation, no romanisation, and no extra punctuation "
            "beyond what naturally belongs in the sentence.\n\n"
            f"English text: {text}"
        )
    script_guidance = (
        "The Hindi may be written in Devanagari or Latin transliteration. "
        if romanized_hindi else "The Hindi text is written in Devanagari script. "
    )
    return (
        "You are a professional Hindi-to-English translator. "
        f"Translate the following Hindi text. {script_guidance}"
        "Return fluent, natural English. "
        "Return ONLY the translated English text with no explanation and no extra punctuation "
        "beyond what naturally belongs in the sentence.\n\n"
        f"Hindi text: {text}"
    )


def _groq_cooldown_seconds(response) -> float:
    retry_after = response.headers.get("Retry-After", "1")
    try:
        try:
            seconds = float(retry_after)
        except ValueError:
            retry_at = parsedate_to_datetime(retry_after)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
        return min(max(seconds, 0.25), _GROQ_MAX_COOLDOWN_SECONDS)
    except (TypeError, ValueError):
        return 1.0


async def _call_groq(text: str, direction: str, romanized_hindi: bool = False) -> str | None:
    """Call hosted Groq inference for the deployed app, with shared 429 recovery."""
    global _GROQ_COOLDOWN_UNTIL, _GROQ_NEXT_REQUEST_AT
    api_key = settings.GROQ_API_KEY.strip()
    if not api_key:
        logger.error("GROQ_API_KEY is not configured; add it to the deployed backend environment.")
        return None

    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [{"role": "user", "content": _translation_prompt(text, direction, romanized_hindi)}],
        "max_tokens": 512,
        "temperature": 0,
    }
    endpoint = f"{settings.GROQ_BASE_URL.rstrip('/')}/chat/completions"

    async with _TRANSLATION_LOCK:
        # One delayed retry per turn; queued turns share the same cooldown and
        # remain serialized across every WebSocket handled by this process.
        for attempt in range(2):
            loop = asyncio.get_running_loop()
            wait_for = max(_GROQ_COOLDOWN_UNTIL, _GROQ_NEXT_REQUEST_AT) - loop.time()
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json=payload,
                    )
                completed_at = loop.time()
                _GROQ_NEXT_REQUEST_AT = completed_at + _GROQ_MIN_INTERVAL_SECONDS
                if response.status_code == 429:
                    cooldown = _groq_cooldown_seconds(response)
                    _GROQ_COOLDOWN_UNTIL = completed_at + cooldown
                    logger.warning("Groq rate limited; shared cooldown %.2fs (attempt %s/2).", cooldown, attempt + 1)
                    if attempt == 0:
                        continue
                    return None
                response.raise_for_status()
                choices = response.json().get("choices") or []
                result = choices[0].get("message", {}).get("content", "").strip() if choices else ""
                if result:
                    logger.info("Groq translation success: direction=%s model=%s", direction, settings.GROQ_MODEL)
                    return result
                logger.warning("Groq returned an empty translation.")
                return None
            except httpx.HTTPStatusError as exc:
                logger.error("Groq API returned HTTP %s: %s", exc.response.status_code, exc.response.text[:500])
                return None
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.error("Groq request failed (%s).", type(exc).__name__)
                return None
            except Exception as exc:
                logger.error("Groq translation failed (%s).", type(exc).__name__)
                return None
    return None


class TranslationService:
    """
    Translation service backed by hosted Groq by default or local Ollama.
    Returns only model translations; failures are surfaced to the turn.
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

        provider = settings.TRANSLATION_PROVIDER.strip().lower()
        provider = "groq" if provider in {"", "auto"} else provider
        translator = _call_groq if provider == "groq" else _call_ollama if provider == "ollama" else None
        if translator is None:
            raise TranslationError(f"Unsupported translation provider '{provider}'. Use 'groq' or 'ollama'.")
        result = await translator(
            clean_text,
            direction,
            romanized_hindi=(source_code == "hi" and not has_hindi),
        )
        if result:
            return result

        logger.warning("Translation unavailable (provider=%s direction=%s).", provider, direction)
        if provider == "groq":
            raise TranslationError("Hosted translation unavailable. Check GROQ_API_KEY, model access, and Groq rate limits.")
        raise TranslationError(f"Local translation unavailable. Ensure Ollama is running and model '{settings.OLLAMA_MODEL}' is installed.")


translation_service = TranslationService()
