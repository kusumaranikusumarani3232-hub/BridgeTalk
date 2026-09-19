import logging
import httpx
from deep_translator import GoogleTranslator
from app.config import settings

logger = logging.getLogger("bridgetalk.translation")

class TranslationService:
    def __init__(self):
        # హాకథాన్ రూల్స్ ప్రకారం అసెంబ్లీAI కీని కాన్ఫిగర్ చేసాము
        self.assemblyai_key = settings.ASSEMBLYAI_API_KEY

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translates text between source_lang and target_lang.
        Handles real-time WebSocket transcript text instantly.
        """
        clean_text = text.strip()
        if not clean_text:
            return ""

        src = source_lang.lower()
        tgt = target_lang.lower()

        # ఒకే భాష అయితే అనువాదం అవసరం లేదు
        if src in tgt or tgt in src:
            return clean_text

        # 🌟 స్టెప్ 1: రియల్-టైమ్ స్ట్రీమింగ్ (Live Turns) కోసం 100% పక్కాగా పనిచేసే ఉచిత అనువాదం
        try:
            translator = GoogleTranslator(source=src, target=tgt)
            translated = translator.translate(clean_text)
            if translated:
                logger.info(f"🎭 Real-time Translated [{src} -> {tgt}]: {translated.strip()}")
                return translated.strip()
        except Exception as e:
            logger.error(f"Fallback DeepTranslator failed: {e}")

        # 🌟 స్టెప్ 2: ఒకవేళ బ్యాకప్ ఫెయిల్ అయితే అసెంబ్లీAI LeMUR ద్వారా ప్రయత్నించడం
        if self.assemblyai_key:
            try:
                src_name = "Hindi" if "hi" in src else "English"
                tgt_name = "Hindi" if "hi" in tgt else "English"

                headers = {
                    "Authorization": self.assemblyai_key.strip(),
                    "Content-Type": "application/json",
                }
                payload = {
                    "prompt": f"Translate this text from {src_name} to {tgt_name}: \"{clean_text}\". Provide only the raw translation.",
                    "final_model": "default"
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post("https://assemblyai.com", headers=headers, json=payload)
                    if resp.status_code == 200:
                        content = resp.json().get("response", "").strip()
                        return content.replace('"', '')
            except Exception as lemur_err:
                logger.warning(f"LeMUR Direct Task failed during stream: {lemur_err}")

        # అత్యవసర ఫాల్‌బ్యాక్: పాత టెక్స్ట్
        return clean_text

translation_service = TranslationService()
