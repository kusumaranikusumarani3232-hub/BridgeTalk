from typing import List, Optional
from pydantic import BaseModel, Field
import time
import uuid

class InsightItem(BaseModel):
    category: str  # e.g., "date", "time", "location", "request", "amount"
    label: str     # e.g., "Date", "Time", "Location", "Meeting Request"
    value: str     # e.g., "Tomorrow", "10:00 AM"
    icon: str      # e.g., "📅", "🕙", "📍", "📌"

class SpeakerConfig(BaseModel):
    id: str        # "person_a" or "person_b"
    name: str      # "Person A" or "Person B"
    language_code: str  # "hi" or "en"
    language_name: str  # "Hindi" or "English"
    flag: str      # "🇮🇳" or "🇬🇧"

class PartialTranscript(BaseModel):
    type: str = "partial"
    speaker: str
    text: str
    timestamp: float = Field(default_factory=time.time)

class FinalMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "final"
    speaker: str
    speaker_name: str
    source_language: str
    target_language: str
    original_text: str
    translation: str
    insights: List[InsightItem] = []
    timestamp: str = Field(default_factory=lambda: time.strftime("%H:%M:%S"))

class StatusUpdate(BaseModel):
    type: str = "status"
    connected: bool
    assemblyai_ready: bool
    speaker: str
    message: str

class TranslationRequest(BaseModel):
    text: str
    source_lang: str  # "hi" or "en"
    target_lang: str  # "en" or "hi"

class TranslationResponse(BaseModel):
    original: str
    translation: str
    source_lang: str
    target_lang: str
