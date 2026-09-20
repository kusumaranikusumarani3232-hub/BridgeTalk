import logging
import re
from deep_translator import GoogleTranslator

logger = logging.getLogger("bridgetalk.translation")

class TranslationService:
    def __init__(self):
        pass

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Ultimate Hackathon Smart Translator.
        Detects pure Hindi vs Hinglish phonetics and forces correct translation.
        """
        clean_text = text.strip()
        if not clean_text:
            return ""

        if clean_text.lower() in ["see.", "see", "okay", "okay."]:
            return "..."

        # 1. టెక్స్ట్‌లో హిందీ అక్షరాలు ఉన్నాయో లేదో చూడటం
        has_hindi_chars = bool(re.search(r"[\u0900-\u097F]", clean_text))

        try:
            if has_hindi_chars:
                # 🌟 ట్రిక్: ఇది ప్యూర్ హిందీనా లేక ఇంగ్లీష్ మాటలను హిందీలో రాశారా (Hinglish) అని చెక్ చేయడం
                # ఉదాహరణకు: "नेम", "व्हाट", "माय", "इस", "कैन", "यू" లాంటి పదాలు ఉంటే అది ఇంగ్లీష్ స్పీకర్ అన్నమాట!
                hinglish_keywords = ["नेम", "व्हाट", "माय", "इस", "कैन", "यू", "टॉक", "विथ", "मी", "हेलो", "हाय"]
                is_hinglish = any(word in clean_text for word in hinglish_keywords)

                if is_hinglish:
                    # ఇంగ్లీష్ వ్యక్తి మాట్లాడిన మాటలు హిందీ అక్షరాల్లో వస్తే, దాన్ని ప్యూర్ హిందీ టెక్స్ట్‌లోకి మార్చాలి!
                    logger.info(f"🔮 Hinglish Detected. Translating to Pure Hindi: {clean_text}")
                    # మొదట దీన్ని ఇంగ్లీషులోకి మార్చి, ఆపై హిందీలోకి పంపిస్తాము
                    to_eng = GoogleTranslator(source="hi", target="en").translate(clean_text)
                    to_hindi = GoogleTranslator(source="en", target="hi").translate(to_eng)
                    return to_hindi.strip()
                else:
                    # ఇది ప్యూర్ హిందీ వ్యక్తి మాట్లాడిన మాట (e.g., "आपका नाम क्या है?"), కాబట్టి ఇంగ్లీషులోకి మార్చాలి!
                    logger.info(f"🔮 Pure Hindi Detected. Translating to English: {clean_text}")
                    translated = GoogleTranslator(source="hi", target="en").translate(clean_text)
                    if translated:
                        return translated.strip()
            else:
                # ఒకవేళ ఇంగ్లీష్ అక్షరాల్లో వస్తే కళ్లు మూసుకుని హిందీలోకి మార్చాలి
                logger.info(f"🔮 English Text Detected. Translating to Hindi: {clean_text}")
                translated = GoogleTranslator(source="en", target="hi").translate(clean_text)
                if translated:
                    return translated.strip()
                    
        except Exception as e:
            logger.error(f"Hackathon smart translation failed: {e}")

        return clean_text

translation_service = TranslationService()
