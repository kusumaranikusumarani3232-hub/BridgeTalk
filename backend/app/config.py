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
    
    # Translation Configuration
    TRANSLATION_API_KEY: str = os.getenv("TRANSLATION_API_KEY", "")
    TRANSLATION_PROVIDER: str = os.getenv("TRANSLATION_PROVIDER", "auto") # auto, openai, deep_translator
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", os.getenv("TRANSLATION_API_KEY", ""))
    
    # Host & Port Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    @property
    def is_assemblyai_configured(self) -> bool:
        """Returns True if AssemblyAI API key is non-empty and valid format."""
        key = self.ASSEMBLYAI_API_KEY.strip()
        return len(key) > 5 and not key.startswith("your_")

settings = Settings()
