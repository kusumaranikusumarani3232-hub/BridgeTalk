import logging
import httpx
from deep_translator import GoogleTranslator
from app.config import settings

logger = logging.getLogger("bridgetalk.translation")

class TranslationService:
    def __init__(self):
        self.openai_key = settings.OPENAI_API_KEY
        self.provider = settings.TRANSLATION_PROVIDER

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translates text between source_lang and target_lang.
        source_lang / target_lang: 'hi' (Hindi), 'en' (English), etc.
        """
        clean_text = text.strip()
        if not clean_text:
            return ""

        # Normalize language codes
        src = source_lang.lower()
        tgt = target_lang.lower()
        if src == tgt:
            return clean_text

        # Try LLM API translation first if configured
        if (self.provider == "openai" or (self.provider == "auto" and self.openai_key)) and self.openai_key:
            try:
                llm_res = await self._translate_with_llm(clean_text, src, tgt)
                if llm_res:
                    return llm_res
            except Exception as e:
                logger.warning(f"LLM translation failed, falling back to translator library: {e}")

        # Fallback to DeepTranslator (free, highly reliable)
        try:
            translator = GoogleTranslator(source=src, target=tgt)
            translated = translator.translate(clean_text)
            if translated:
                return translated.strip()
        except Exception as e:
            logger.error(f"DeepTranslator failed: {e}")

        # Emergency fallback: return original text
        return clean_text

    async def _translate_with_llm(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translates text using an OpenAI-compatible Chat Completions API.
        """
        src_name = "Hindi" if source_lang == "hi" else "English"
        tgt_name = "English" if source_lang == "hi" else "Hindi"

        system_prompt = (
            f"You are a professional conversational real-time translator from {src_name} to {tgt_name}.\n"
            "Rules:\n"
            "1. Translate the user text accurately while preserving conversational tone.\n"
            "2. Strictly preserve all names, numbers, dates, times, locations, and currency amounts.\n"
            "3. Do NOT add any explanations, notes, metadata, prefix, suffix, or extra text.\n"
            "4. Return ONLY the translated string."
        )

        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.1,
            "max_tokens": 500,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                # Clean any quotes wrapping result
                if content.startswith('"') and content.endswith('"'):
                    content = content[1:-1].strip()
                return content
            else:
                logger.error(f"OpenAI API error: status {resp.status_code}, response: {resp.text}")
                return ""

translation_service = TranslationService()
