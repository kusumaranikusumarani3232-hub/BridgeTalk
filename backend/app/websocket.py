import asyncio
import json
import logging
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
        
        # Speaker State
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
        
        # Initial status broadcast
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
                    # Client disconnected abruptly
                    break

                # Detect disconnect message type
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
                        if speaker in self.speaker_configs:
                            self.active_speaker = speaker
                            cfg = self.speaker_configs[speaker]
                            logger.info(f"Active speaker set to: {speaker} ({cfg['name']})")
                            await self.send_status(
                                connected=True,
                                assemblyai_ready=self.assemblyai_service.is_connected,
                                message=f"Active speaker: {cfg['name']} ({cfg['source_name']} → {cfg['target_name']})"
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
        """Starts real-time session by connecting to AssemblyAI API."""
        if self.is_session_active:
            return

        self.is_session_active = True
        logger.info("Starting AssemblyAI audio transcription session...")

        success = await self.assemblyai_service.connect(
            on_partial=self.on_partial_transcript,
            on_final=self.on_final_transcript,
            on_status=self.on_assemblyai_status
        )

        if not success:
            self.is_session_active = False

    async def stop_session(self):
        """Stops real-time session and closes AssemblyAI connection cleanly."""
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
        """Callback when partial transcript received from AssemblyAI."""
        msg = PartialTranscript(
            speaker=self.active_speaker,
            text=text
        )
        try:
            await self.websocket.send_text(msg.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to send partial transcript to frontend: {e}")

    async def on_final_transcript(self, text: str):
        """Callback when finalized transcript received from AssemblyAI."""
        cfg = self.speaker_configs[self.active_speaker]
        src_lang = cfg["source_lang"]
        tgt_lang = cfg["target_lang"]

        # Translate finalized utterance
        translation = await translation_service.translate(text, src_lang, tgt_lang)
        
        # Extract structured insights
        insights = insights_service.extract_insights(text, translation)

        final_msg = FinalMessage(
            speaker=self.active_speaker,
            speaker_name=cfg["name"],
            source_language=cfg["source_name"],
            target_language=cfg["target_name"],
            original_text=text,
            translation=translation,
            insights=insights
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
        """
        Executes a simulated credit-free conversation sequence for live presentations.
        """
        logger.info("Executing Demo Mode conversation sequence...")
        await self.send_status(
            connected=True,
            assemblyai_ready=True,
            message="Demo Mode active — displaying pre-recorded example."
        )

        demo_turns = [
            {
                "speaker": "person_a",
                "partials": [
                    "Namaste...",
                    "Namaste, kya aap kal meeting...",
                    "Namaste, kya aap kal meeting ke liye das baje aa sakte hain?"
                ],
                "final": "Namaste, kya aap kal meeting ke liye das baje aa sakte hain?",
                "translation": "Hello, can you come at ten o'clock tomorrow for the meeting?",
            },
            {
                "speaker": "person_b",
                "partials": [
                    "Yes, I...",
                    "Yes, I can come at ten...",
                    "Yes, I can come at ten tomorrow."
                ],
                "final": "Yes, I can come at ten tomorrow.",
                "translation": "हाँ, मैं कल दस बजे आ सकता हूँ।",
            }
        ]

        for turn in demo_turns:
            self.active_speaker = turn["speaker"]
            cfg = self.speaker_configs[self.active_speaker]

            # Stream partials
            for p_text in turn["partials"]:
                await self.on_partial_transcript(p_text)
                await asyncio.sleep(0.6)

            # Send final
            insights = insights_service.extract_insights(turn["final"], turn["translation"])
            final_msg = FinalMessage(
                speaker=self.active_speaker,
                speaker_name=cfg["name"],
                source_language=cfg["source_name"],
                target_language=cfg["target_name"],
                original_text=turn["final"],
                translation=turn["translation"],
                insights=insights
            )
            await self.websocket.send_text(final_msg.model_dump_json())
            await asyncio.sleep(1.2)
