import logging
import httpx
from app.config import settings

logger = logging.getLogger("bridgetalk.translation")

class TranslationService:
    def __init__(self):
        # హాకథాన్ నిబంధనల ప్రకారం అసెంబ్లీAI కీ మాత్రమే వాడుతున్నాము
        self.assemblyai_key = settings.ASSEMBLYAI_API_KEY

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translates text between source_lang and target_lang using AssemblyAI LeMUR Task API.
        """
        clean_text = text.strip()
        if not clean_text:
            return ""

        src = source_lang.lower()
        tgt = target_lang.lower()

        # రెండు భాషలు ఒకటే అయితే అనువాదం అవసరం లేదు
        if src in tgt or tgt in src:
            return clean_text

        if not self.assemblyai_key:
            logger.error("AssemblyAI API Key missing for LeMUR Translation.")
            return clean_text

        try:
            src_name = "Hindi" if "hi" in src else "English"
            tgt_name = "Hindi" if "hi" in tgt else "English"

            system_instruction = (
                f"You are a professional real-time translator from {src_name} to {tgt_name}.\n"
                "Rules:\n"
                f"1. Translate the user text accurately into fluent {tgt_name}.\n"
                "2. Strictly preserve all names, numbers, dates, times, locations.\n"
                "3. Do NOT add any explanations, introductory notes, or extra punctuation.\n"
                "4. Return ONLY the final translated string."
            )

            headers = {
                "Authorization": self.assemblyai_key.strip(),
                "Content-Type": "application/json",
            }

            payload = {
                "prompt": f"{system_instruction}\n\nText to translate:\n\"{clean_text}\"",
                "final_model": "default"
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post("https://assemblyai.com", headers=headers, json=payload)
                
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("response", "").strip()
                    
                    if content.startswith('"') and content.endswith('"'):
                        content = content[1:-1].strip()
                        
                    logger.info(f"LeMUR Translated [{src_name} -> {tgt_name}]: {content}")
                    return content
                else:
                    logger.error(f"AssemblyAI LeMUR Error: Status {resp.status_code}, Response: {resp.text}")
                    return clean_text

        except Exception as e:
            logger.error(f"LeMUR translation request failed: {e}")
            return clean_text

translation_service = TranslationService()
