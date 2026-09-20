import logging
import re
from deep_translator import GoogleTranslator

logger = logging.getLogger("bridgetalk.translation")

class TranslationService:
    def __init__(self):
        pass

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Absolute Forced Real-time Text Translator for Hackathon.
        Ignores language code bugs and directly targets text script character sets.
        """
        clean_text = text.strip()
        if not clean_text:
            return ""

        # అసెంబ్లీAI కొన్నిసార్లు ఇచ్చే "See." లేదా మైక్ నాయిస్ పదాలను ఫిల్టర్ చేయడం
        if clean_text.lower() in ["see.", "see", "okay", "okay.", "ठीक"]:
            # ఇవి వస్తే అనువాదం కాకుండా క్లీన్ టెక్స్ట్ ఇస్తాము
            return "..."

        # 1. టెక్స్ట్‌లో హిందీ/దేవనాగరి అక్షరాలు ఉన్నాయో లేదో పరీక్షించడం
        has_hindi_chars = bool(re.search(r"[\u0900-\u097F]", clean_text))

        try:
            if has_hindi_chars:
                # హిందీ అక్షరాలు కనిపిస్తే.. కళ్లు మూసుకుని ఇంగ్లీషులోకి మార్చాలి!
                logger.info(f"🤖 Hard Forcing [Hindi -> English] for: {clean_text}")
                translator = GoogleTranslator(source="hi", target="en")
                translated = translator.translate(clean_text)
                if translated:
                    return translated.strip()
            else:
                # ఇంగ్లీష్ అక్షరాలు కనిపిస్తే.. కళ్లు మూసుకుని హిందీలోకి మార్చాలి!
                logger.info(f"🤖 Hard Forcing [English -> Hindi] for: {clean_text}")
                translator = GoogleTranslator(source="en", target="hi")
                translated = translator.translate(clean_text)
                if translated:
                    return translated.strip()
                    
        except Exception as e:
            logger.error(f"💥 Forced Hackathon Translation execution failed: {e}")

        return clean_text

translation_service = TranslationService()
