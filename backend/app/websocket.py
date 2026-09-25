import asyncio
import json
import logging
import re
from fastapi import WebSocket, WebSocketDisconnect
from app.assemblyai_service import AssemblyAIService
from app.translation_service import translation_service
from app.insights_service import insights_service
from app.models import FinalMessage, PartialTranscript, StatusUpdate
from app.config import settings

logger = logging.getLogger("bridgetalk.websocket")

class WebSocketHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.assemblyai_service = AssemblyAIService()
        
        self.active_speaker = "person_a"  # "person_a" (Hindi) or "person_b" (English)
        self.speaker_configs = {
            "person_a": {
                "name": "Person A",
                "source_lang": "hi",
                "source_name": "Hindi",
                "target_lang": "en",
                "target_name": "English",
                "flag": "🇮🇳"
            },
            "person_b": {
                "name": "Person B",
                "source_lang": "en",
                "source_name": "English",
                "target_lang": "hi",
                "target_name": "Hindi",
                "flag": "🇬🇧"
            }
        }
        self.is_session_active = False

    async def handle(self):
        await self.websocket.accept()
        logger.info("Client WebSocket connected.")
        
        try:
            await self.send_status(
                connected=True,
                assemblyai_ready=settings.is_assemblyai_configured,
                message="Client connected. Click Start Conversation to activate mic."
            )
        except Exception:
            pass

        try:
            while True:
                try:
                    message = await self.websocket.receive()
                except Exception:
                    break

                if message.get("type") == "websocket.disconnect":
                    break

                # 1. Handle JSON Control Messages
                if "text" in message and message["text"]:
                    try:
                        data = json.loads(message["text"])
                    except json.JSONDecodeError:
                        continue
                    action = data.get("action")

                    if action == "start":
                        await self.start_session()
                    elif action == "stop":
                        await self.stop_session()
                    elif action == "set_speaker":
                        speaker = data.get("speaker", "person_a")
                        if speaker in self.speaker_configs and speaker != self.active_speaker:
                            self.active_speaker = speaker
                            cfg = self.speaker_configs[speaker]
                            logger.info(f"Switching active speaker to: {speaker} ({cfg['name']})")
                            
                            # 🌟 అత్యంత ముఖ్యం: స్పీకర్ మారినప్పుడు అసెంబ్లీAI వెబ్‌సాకెట్‌ను కొత్త లాంగ్వేజ్‌తో రీస్టార్ట్ చేయడం
                            if self.is_session_active:
                                logger.info("Re-connecting AssemblyAI stream with new language context...")
                                await self.assemblyai_service.disconnect()
                                
                                current_lang = cfg["source_lang"]
                                success = await self.assemblyai_service.connect(
                                    on_partial=self.on_partial_transcript,
                                    on_final=self.on_final_transcript,
                                    on_status=self.on_assemblyai_status,
                                    language_code=current_lang
                                )
                                if not success:
                                    self.is_session_active = False

                            await self.send_status(
                                connected=True,
                                assemblyai_ready=self.assemblyai_service.is_connected,
                                message=f"Active speaker updated: {cfg['name']} ({cfg['source_name']} → {cfg['target_name']})"
                            )
                    elif action == "start_demo":
                        asyncio.create_task(self.run_demo_mode())

                # 2. Handle Binary PCM Audio Frames
                elif "bytes" in message and message["bytes"]:
                    if self.is_session_active and self.assemblyai_service.is_connected:
                        await self.assemblyai_service.send_audio_chunk(message["bytes"])

        except WebSocketDisconnect:
            logger.info("Client WebSocket disconnected.")
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        finally:
            await self.stop_session()

    async def start_session(self):
        """Starts real-time session by connecting to AssemblyAI API with correct language."""
        if self.is_session_active:
            return

        self.is_session_active = True
        
        cfg = self.speaker_configs[self.active_speaker]
        current_lang = cfg["source_lang"]
        
        logger.info(f"Starting AssemblyAI session for language: {current_lang}...")

        success = await self.assemblyai_service.connect(
            on_partial=self.on_partial_transcript,
            on_final=self.on_final_transcript,
            on_status=self.on_assemblyai_status,
            language_code=current_lang
        )

        if not success:
            self.is_session_active = False

    async def stop_session(self):
        if not self.is_session_active:
            return

        self.is_session_active = False
        await self.assemblyai_service.disconnect()
        await self.send_status(
            connected=True,
            assemblyai_ready=False,
            message="Session stopped. AssemblyAI connection closed."
        )

    async def on_partial_transcript(self, text: str):
        msg = PartialTranscript(
            speaker=self.active_speaker,
            text=text
        )
        try:
            await self.websocket.send_text(msg.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to send partial transcript to frontend: {e}")

    async def on_final_transcript(self, text: str):
        """
        Routes the final transcript through the translation service. Devanagari
        transcripts are Hindi; otherwise the selected speaker's language is used,
        which also supports romanized Hindi from Person A.
        """
        clean_text = text.strip()
        if not clean_text:
            return

        cfg = self.speaker_configs[self.active_speaker]

        has_hindi_script = bool(re.search(r"[\u0900-\u097F]", clean_text))
        if has_hindi_script:
            source_lang, target_lang = "hi", "en"
            source_name, target_name = "Hindi", "English"
        else:
            source_lang, target_lang = cfg["source_lang"], cfg["target_lang"]
            source_name, target_name = cfg["source_name"], cfg["target_name"]

        # Call the translation service (with instant fallback map for common phrases).
        try:
            translation = await translation_service.translate(
                text=clean_text,
                source_lang=source_lang,
                target_lang=target_lang,
            )
        except Exception as exc:
            logger.error(f"translation_service.translate error: {exc}")
            translation = clean_text

        display_original = clean_text
        display_translation = translation

        insights = insights_service.extract_insights(display_original, display_translation)

        final_msg = FinalMessage(
            speaker=self.active_speaker,
            speaker_name=cfg["name"],
            source_language=source_name,
            target_language=target_name,
            original_text=display_original,
            translation=display_translation,
            insights=insights,
        )

        try:
            await self.websocket.send_text(final_msg.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to send final transcript to frontend: {e}")


    async def on_assemblyai_status(self, message: str, ready: bool):
        await self.send_status(
            connected=True,
            assemblyai_ready=ready,
            message=message
        )

    async def send_status(self, connected: bool, assemblyai_ready: bool, message: str):
        status = StatusUpdate(
            connected=connected,
            assemblyai_ready=assemblyai_ready,
            speaker=self.active_speaker,
            message=message
        )
        try:
            await self.websocket.send_text(status.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to send status update: {e}")

    async def run_demo_mode(self):
        logger.info("Executing Demo Mode conversation sequence...")
        await self.send_status(
            connected=True,
            assemblyai_ready=True,
            message="Demo Mode active — displaying pre-recorded example."
        )
