import os
from pathlib import Path
from dotenv import load_dotenv

# Find root directory (parent of backend folder if running from root or inside backend)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


class Settings:
    PROJECT_NAME: str = "BridgeTalk"
    PROJECT_TAGLINE: str = "Real-time conversations without language barriers."
    VERSION: str = "1.0.0"
    
    # AssemblyAI Configuration
    ASSEMBLYAI_API_KEY: str = os.getenv("ASSEMBLYAI_API_KEY", "")
    ASSEMBLYAI_WEBSOCKET_URL: str = os.getenv(
        "ASSEMBLYAI_WEBSOCKET_URL", 
        "wss://streaming.assemblyai.com/v3/ws?sample_rate=16000&speech_model=universal-3-5-pro"
    )
    SAMPLE_RATE: int = 16000
    
    # Hosted Groq is the default for the deployed app; Ollama remains available locally.
    TRANSLATION_PROVIDER: str = os.getenv("TRANSLATION_PROVIDER", "groq").strip().lower()
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    
    # Host & Port Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    @property
    def is_assemblyai_configured(self) -> bool:
        """Returns True if AssemblyAI API key is non-empty and valid format."""
        key = self.ASSEMBLYAI_API_KEY.strip()
        return len(key) > 5 and not key.startswith("your_")

settings = Settings()
