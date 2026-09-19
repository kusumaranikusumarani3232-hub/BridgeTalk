import asyncio
import json
import logging
import websockets
from typing import Callable, Optional, Awaitable
from app.config import settings

logger = logging.getLogger("bridgetalk.assemblyai")

class AssemblyAIService:
    def __init__(self):
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.receiver_task: Optional[asyncio.Task] = None
        self.is_connected: bool = False

    async def connect(
        self,
        on_partial: Callable[[str], Awaitable[None]],
        on_final: Callable[[str], Awaitable[None]],
        on_status: Callable[[str, bool], Awaitable[None]],
        language_code: str = "en"  # కరెక్ట్ భాషను గుర్తించడానికి యాడ్ చేసాము
    ) -> bool:
        """
        Establishes a raw WebSocket connection to AssemblyAI Realtime STT v3 API.
        """
        if not settings.is_assemblyai_configured:
            logger.error("AssemblyAI API key is missing or invalid.")
            await on_status("AssemblyAI API key missing in backend configuration.", False)
            return False

        headers = {
            "Authorization": settings.ASSEMBLYAI_API_KEY.strip()
        }

        url = settings.ASSEMBLYAI_WEBSOCKET_URL
        if "speech_model=" not in url:
            delimiter = "&" if "?" in url else "?"
            url = f"{url}{delimiter}speech_model=universal-3-5-pro"
        if "sample_rate=" not in url:
            delimiter = "&" if "?" in url else "?"
            url = f"{url}{delimiter}sample_rate=16000"
            
        # అసెంబ్లీAI కి లాంగ్వేజ్ కోడ్‌ని పంపుతున్నాము
        delimiter = "&" if "?" in url else "?"
        url = f"{url}{delimiter}language_code={language_code}"

        try:
            logger.info(f"Connecting to AssemblyAI Realtime WebSocket: {url}")
            self.ws = await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10
            )
            self.is_connected = True
            logger.info("Successfully connected to AssemblyAI Realtime API.")
            await on_status("Connected to AssemblyAI Realtime API", True)

            self.receiver_task = asyncio.create_task(
                self._receive_loop(on_partial, on_final, on_status)
            )
            return True

        except Exception as e:
            logger.error(f"Failed to connect to AssemblyAI WebSocket: {e}")
            self.is_connected = False
            await on_status(f"AssemblyAI Connection Error: {str(e)}", False)
            return False

    async def send_audio_chunk(self, pcm_data: bytes):
        if self.ws and self.is_connected:
            try:
                await self.ws.send(pcm_data)
            except Exception as e:
                logger.error(f"Error streaming audio to AssemblyAI: {e}")
                self.is_connected = False

    async def disconnect(self):
        if self.ws and self.is_connected:
            logger.info("Sending Terminate signal to AssemblyAI...")
            try:
                await self.ws.send(json.dumps({"type": "Terminate"}))
                await asyncio.sleep(0.1)
                await self.ws.close()
            except Exception as e:
                logger.warning(f"Error during AssemblyAI disconnect: {e}")
            finally:
                self.is_connected = False
                self.ws = None

        if self.receiver_task and not self.receiver_task.done():
            self.receiver_task.cancel()
            self.receiver_task = None
        logger.info("AssemblyAI session closed cleanly.")

    async def _receive_loop(
        self,
        on_partial: Callable[[str], Awaitable[None]],
        on_final: Callable[[str], Awaitable[None]],
        on_status: Callable[[str, bool], Awaitable[None]],
    ):
        try:
            while self.ws and self.is_connected:
                msg_raw = await self.ws.recv()
                if isinstance(msg_raw, bytes):
                    continue

                data = json.loads(msg_raw)
                msg_type = data.get("type")

                if msg_type == "Begin":
                    session_id = data.get("id")
                    logger.info(f"AssemblyAI Session Started. ID: {session_id}")
                    await on_status("AssemblyAI Session Ready", True)

                elif msg_type == "Turn":
                    text = data.get("transcript", "").strip()
                    end_of_turn = data.get("end_of_turn", False)

                    if text:
                        if end_of_turn:
                            logger.info(f"Final Transcript: {text}")
                            await on_final(text)
                        else:
                            await on_partial(text)

                elif msg_type == "SpeechStarted":
                    logger.debug("AssemblyAI: Speech detected.")

                elif msg_type == "Termination":
                    logger.info("AssemblyAI sent Termination event.")
                    self.is_connected = False
                    break

                elif msg_type == "Error":
                    error_msg = data.get("error", "Unknown AssemblyAI Error")
                    logger.error(f"AssemblyAI Error Event: {error_msg}")
                    await on_status(f"AssemblyAI Error: {error_msg}", False)

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"AssemblyAI WebSocket closed: {e}")
            self.is_connected = False
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in AssemblyAI receiver loop: {e}")
            self.is_connected = False
            await on_status(f"AssemblyAI stream disconnected: {str(e)}", False)
