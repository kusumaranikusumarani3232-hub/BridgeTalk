import logging
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.models import TranslationRequest, TranslationResponse
from app.translation_service import translation_service
from app.websocket import WebSocketHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_TAGLINE,
    version=settings.VERSION
)

# Configure CORS for local development and frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    """Health check endpoint exposing system status without revealing secrets."""
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "tagline": settings.PROJECT_TAGLINE,
        "version": settings.VERSION,
        "assemblyai_configured": settings.is_assemblyai_configured,
        "translation_provider": settings.TRANSLATION_PROVIDER
    }

@app.post("/api/translate", response_model=TranslationResponse)
async def translate_text(req: TranslationRequest):
    """Direct translation endpoint for ad-hoc queries."""
    translated = await translation_service.translate(
        req.text, req.source_lang, req.target_lang
    )
    return TranslationResponse(
        original=req.text,
        translation=translated,
        source_lang=req.source_lang,
        target_lang=req.target_lang
    )

@app.get("/api/demo-data")
async def get_demo_data():
    """Returns sample pre-recorded conversation messages for demo mode."""
    return [
        {
            "id": "demo-1",
            "type": "final",
            "speaker": "person_a",
            "speaker_name": "Person A",
            "source_language": "Hindi",
            "target_language": "Hindi",
            "original_text": "Kal meeting ke liye aap das baje aa sakte hain?",
            "translation": "Can you come at ten tomorrow for the meeting?",
            "timestamp": "10:00:00",
            "insights": [
                {"category": "date", "label": "Date", "value": "Tomorrow", "icon": "📅"},
                {"category": "time", "label": "Time", "value": "10:00 AM", "icon": "🕙"},
                {"category": "topic", "label": "Topic", "value": "Meeting", "icon": "📌"}
            ]
        },
        {
            "id": "demo-2",
            "type": "final",
            "speaker": "person_b",
            "speaker_name": "Person B",
            "source_language": "English",
            "target_language": "English",
            "original_text": "Yes, I can come at ten.",
            "translation": "हाँ, मैं दस बजे आ सकता हूँ।",
            "timestamp": "10:00:15",
            "insights": [
                {"category": "time", "label": "Time", "value": "10:00 AM", "icon": "🕙"}
            ]
        }
    ]

@app.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming and transcripts."""
    handler = WebSocketHandler(websocket)
    await handler.handle()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
