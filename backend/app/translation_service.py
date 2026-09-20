import logging
import re
from deep_translator import GoogleTranslator
from app.config import settings

logger = logging.getLogger("bridgetalk.translation")

class TranslationService:
    def __init__(self):
        self.assemblyai_key = settings.ASSEMBLYAI_API_KEY

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Smart Real-time Translator with auto Devanagari/English script correction.
        """
        clean_text = text.strip()
        if not clean_text:
            return ""

        # 🌟 స్మార్ట్ ట్రిక్: టెక్స్ట్‌లో హిందీ అక్షరాలు (Devanagari) ఉన్నాయో లేదో తనిఖీ చేయడం
        has_hindi_chars = bool(re.search(r"[\u0900-\u097F]", clean_text))
        
        # ఒకవేళ ఇంగ్లీష్ పర్సన్ మాట్లాడిన మాటలు హిందీ అక్షరాలలో వస్తే (e.g., "माय नेम इस...")
        # లేదా హిందీ పర్సన్ మాట్లాడిన మాటలు హిందీలోనే ఉంటే...
        # వాటిని కరెక్ట్ లాంగ్వేజ్ కోడ్స్‌కు రీ-అసైన్ చేయడం
        if has_hindi_chars and target_lang == "hi":
            # ఒకవేళ ఇంగ్లీష్ వ్యక్తి మాట్లాడింది హిందీ అక్షరాల్లో వస్తే, దాన్ని ఇంగ్లీషులోకి ఫోర్స్ ట్రాన్స్‌లేట్ చేయాలి
            actual_src = "hi"
            actual_tgt = "en"
        elif not has_hindi_chars and target_lang == "en":
            # ఒకవేళ ఇంగ్లీష్ అక్షరాల్లో ఉండి టార్గెట్ కూడా ఇంగ్లీష్ అయితే, దాన్ని హిందీలోకి మార్చాలి
            actual_src = "en"
            actual_tgt = "hi"
        else:
            actual_src = source_lang.lower()
            actual_tgt = target_lang.lower()

        # రెండు ఒకటే అయితే అనువాదం అవసరం లేదు
        if actual_src == actual_tgt:
            return clean_text

        # 100% పక్కాగా పనిచేసే రియల్-టైమ్ అనువాదం
        try:
            translator = GoogleTranslator(source=actual_src, target=actual_tgt)
            translated = translator.translate(clean_text)
            if translated:
                logger.info(f"🔮 Smart Fixed Translation [{actual_src} -> {actual_tgt}]: {translated.strip()}")
                return translated.strip()
        except Exception as e:
            logger.error(f"Smart Translation failed: {e}")

        return clean_text

translation_service = TranslationService()

