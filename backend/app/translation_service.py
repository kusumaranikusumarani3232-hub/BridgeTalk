import logging
import re
from deep_translator import GoogleTranslator

logger = logging.getLogger("bridgetalk.translation")

class TranslationService:
    def __init__(self):
        pass

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Absolute Forced Real-time Translator for Hackathon.
        Ignores broken variable states and translates based on text script detection.
        """
        clean_text = text.strip()
        if not clean_text:
            return ""

        # 1. టెక్స్ట్‌లో హిందీ/దేవనాగరి అక్షరాలు ఉన్నాయో లేదో చెక్ చేయడం
        has_hindi_chars = bool(re.search(r"[\u0900-\u097F]", clean_text))

        try:
            if has_hindi_chars:
                # హిందీ అక్షరాలు ఉంటే, వేరియబుల్స్ ఏమున్నా సరే.. ఖచ్చితంగా ఇంగ్లీషులోకి మార్చాలి!
                logger.info(f"Forcing Hindi -> English translation for: {clean_text}")
                translator = GoogleTranslator(source="hi", target="en")
                translated = translator.translate(clean_text)
                if translated:
                    return translated.strip()
            else:
                # ఇంగ్లీష్ అక్షరాలు ఉంటే, ఖచ్చితంగా హిందీలోకి మార్చాలి!
                logger.info(f"Forcing English -> Hindi translation for: {clean_text}")
                translator = GoogleTranslator(source="en", target="hi")
                translated = translator.translate(clean_text)
                if translated:
                    return translated.strip()
                    
        except Exception as e:
            logger.error(f"Forced Hackathon Translation failed: {e}")

        # ఏదీ కాకపోతే ఒరిజినల్ టెక్స్ట్
        return clean_text

translation_service = TranslationService()
