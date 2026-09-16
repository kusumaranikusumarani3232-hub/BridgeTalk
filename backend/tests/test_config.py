from app.config import settings

def test_settings_properties():
    assert settings.PROJECT_NAME == "BridgeTalk"
    assert settings.SAMPLE_RATE == 16000
    # Key validation check method
    assert isinstance(settings.is_assemblyai_configured, bool)
