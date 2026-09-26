import asyncio
import json
import logging
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
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
        self.client_connected = True
        # One turn can be translating while up to sixteen finalized turns wait.
        # Overflow fails promptly instead of building latency behind the LLM.
        self.translation_queue = asyncio.Queue(maxsize=16)
        self.translation_worker = None
        self.seen_final_keys = set()

    def _socket_open(self):
        if not self.client_connected:
            return False
        client_state = getattr(self.websocket, "client_state", WebSocketState.CONNECTED)
        app_state = getattr(self.websocket, "application_state", WebSocketState.CONNECTED)
        return client_state == WebSocketState.CONNECTED and app_state == WebSocketState.CONNECTED

    def _callbacks_for_speaker(self, speaker):
        async def partial(text):
            await self.on_partial_transcript(text, speaker)
        async def final(text, metadata=None):
            await self.on_final_transcript(text, speaker, metadata or {})
        return partial, final

    async def handle(self):
        await self.websocket.accept()
        self.client_connected = True
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
                            self.seen_final_keys.clear()
                            cfg = self.speaker_configs[speaker]
                            logger.info(f"Switching active speaker to: {speaker} ({cfg['name']})")
                            
                            # 🌟 అత్యంత ముఖ్యం: స్పీకర్ మారినప్పుడు అసెంబ్లీAI వెబ్‌సాకెట్‌ను కొత్త లాంగ్వేజ్‌తో రీస్టార్ట్ చేయడం
                            if self.is_session_active:
                                logger.info("Re-connecting AssemblyAI stream with new language context...")
                                await self.assemblyai_service.disconnect()
                                
                                current_lang = cfg["source_lang"]
                                partial_cb, final_cb = self._callbacks_for_speaker(speaker)
                                success = await self.assemblyai_service.connect(
                                    on_partial=partial_cb,
                                    on_final=final_cb,
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
            self.client_connected = False
            await self.stop_session()

    async def start_session(self):
        """Starts real-time session by connecting to AssemblyAI API with correct language."""
        if self.is_session_active:
            return

        self.is_session_active = True
        self.seen_final_keys.clear()
        
        cfg = self.speaker_configs[self.active_speaker]
        self.translation_worker = asyncio.create_task(self._translation_worker())
        partial_cb, final_cb = self._callbacks_for_speaker(self.active_speaker)
        current_lang = cfg["source_lang"]
        
        logger.info(f"Starting AssemblyAI session for language: {current_lang}...")

        success = await self.assemblyai_service.connect(
            on_partial=partial_cb,
            on_final=final_cb,
            on_status=self.on_assemblyai_status,
            language_code=current_lang
        )

        if not success:
            self.is_session_active = False

    async def stop_session(self):
        self.is_session_active = False
        await self.assemblyai_service.disconnect()
        if not self.client_connected and self.translation_worker:
            self.translation_worker.cancel()
            await asyncio.gather(self.translation_worker, return_exceptions=True)
            self.translation_worker = None
            while not self.translation_queue.empty():
                try:
                    self.translation_queue.get_nowait()
                    self.translation_queue.task_done()
                except asyncio.QueueEmpty:
                    break
        if self._socket_open():
            await self.send_status(
                connected=True,
                assemblyai_ready=False,
                message="Session stopped. AssemblyAI connection closed."
            )

    async def on_partial_transcript(self, text: str, speaker=None):
        msg = PartialTranscript(
            speaker=speaker or self.active_speaker,
            text=text
        )
        try:
            if self._socket_open():
                await self.websocket.send_text(msg.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to send partial transcript to frontend: {e}")

    async def on_final_transcript(self, text: str, speaker=None, metadata=None):
        """
        Queues one immutable final turn using the speaker bound to this ASR stream.
        """
        clean_text = text.strip()
        if not clean_text:
            return

        speaker = speaker or self.active_speaker
        cfg = self.speaker_configs[speaker]
        # Deduplicate retried final events by provider turn order where available.
        metadata = metadata or {}
        turn_identity = metadata.get("turn_id") or metadata.get("id") or metadata.get("turn_order")
        event_key = f"{speaker}:{turn_identity}" if turn_identity is not None else None
        if event_key and event_key in self.seen_final_keys:
            return
        if event_key:
            self.seen_final_keys.add(event_key)
        turn_id = str(uuid.uuid4())
        turn = {"id": turn_id, "speaker": speaker, "cfg": cfg, "text": clean_text}
        if not self._socket_open():
            return
        logger.info("TURN_ID=%s speaker=%s source_language=%s source_text=%s target_language=%s translated_text= translation_status=pending", turn_id, speaker, cfg["source_name"], clean_text, cfg["target_name"])
        await self._send_turn_result(turn, "pending")
        if not self.translation_worker or self.translation_worker.done():
            self.translation_worker = asyncio.create_task(self._translation_worker())
        try:
            self.translation_queue.put_nowait(turn)
        except asyncio.QueueFull:
            # Drop the oldest pending turn to keep the live conversation fresh.
            stale_turn = self.translation_queue.get_nowait()
            self.translation_queue.task_done()
            await self._send_turn_result(stale_turn, "failed")
            self.translation_queue.put_nowait(turn)

    async def _send_turn_result(self, turn, status, translation=""):
        if not self._socket_open():
            return
        cfg = turn["cfg"]
        final_msg = FinalMessage(
            id=turn["id"], turn_id=turn["id"], speaker=turn["speaker"], speaker_name=cfg["name"],
            source_language=cfg["source_name"], target_language=cfg["target_name"],
            original_text=turn["text"], translation=translation, translated_text=translation,
            translation_status=status,
            insights=insights_service.extract_insights(turn["text"], translation) if translation else [],
        )
        try:
            await self.websocket.send_text(final_msg.model_dump_json())
        except Exception as exc:
            logger.error("Failed to send final TURN_ID=%s: %s", turn["id"], exc)

    async def _translation_worker(self):
        while True:
            turn = await self.translation_queue.get()
            cfg = turn["cfg"]
            translation = ""
            status = "translated"
            try:
                try:
                    if self._socket_open():
                        translation = await translation_service.translate(turn["text"], cfg["source_lang"], cfg["target_lang"])
                        if not translation or translation.strip() in {"...", "…"} or translation == turn["text"]:
                            raise ValueError("Translation returned no distinct translated text")
                        logger.info("TURN_ID=%s speaker=%s source_language=%s source_text=%s target_language=%s translated_text=%s translation_status=translated", turn["id"], turn["speaker"], cfg["source_name"], turn["text"], cfg["target_name"], translation)
                except Exception as exc:
                    status = "failed"
                    logger.error("TURN_ID=%s speaker=%s source_language=%s source_text=%s target_language=%s translated_text= translation_status=failed error=%s", turn["id"], turn["speaker"], cfg["source_name"], turn["text"], cfg["target_name"], exc)
                await self._send_turn_result(turn, status, translation)
            finally:
                self.translation_queue.task_done()


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
            if self._socket_open():
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
