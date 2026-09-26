import asyncio

import pytest

from app import translation_service as translation_module
from app.translation_service import TranslationError, translation_service


@pytest.fixture(autouse=True)
def reset_translation_state(monkeypatch):
    monkeypatch.setattr(translation_module.settings, "TRANSLATION_PROVIDER", "ollama")
    monkeypatch.setattr(translation_module, "_TRANSLATION_LOCK", asyncio.Lock())
    translation_module._GROQ_COOLDOWN_UNTIL = 0
    translation_module._GROQ_NEXT_REQUEST_AT = 0


@pytest.mark.asyncio
async def test_same_language_translation_is_passthrough():
    assert await translation_service.translate("Hello world", "en", "en") == "Hello world"


@pytest.mark.asyncio
async def test_empty_translation_does_not_call_ollama(monkeypatch):
    async def unexpected(*args, **kwargs):
        raise AssertionError("Ollama should not be called for empty input")

    monkeypatch.setattr(translation_module, "_call_ollama", unexpected)
    assert await translation_service.translate("  ", "hi", "en") == ""


@pytest.mark.asyncio
async def test_hindi_to_english_uses_local_ollama(monkeypatch):
    calls = []

    async def ollama(text, direction, romanized_hindi=False):
        calls.append((text, direction, romanized_hindi))
        return "What is here?"

    monkeypatch.setattr(translation_module, "_call_ollama", ollama)
    result = await translation_service.translate("यहाँ क्या है?", "hi", "en")
    assert result == "What is here?"
    assert calls == [("यहाँ क्या है?", "hi_to_en", False)]


@pytest.mark.asyncio
async def test_english_to_hindi_uses_local_ollama(monkeypatch):
    calls = []

    async def ollama(text, direction, romanized_hindi=False):
        calls.append((text, direction))
        return "पानी पियो।"

    monkeypatch.setattr(translation_module, "_call_ollama", ollama)
    result = await translation_service.translate("Drink water.", "en", "hi")
    assert result == "पानी पियो।"
    assert calls == [("Drink water.", "en_to_hi")]


@pytest.mark.asyncio
async def test_ollama_request_uses_configured_model_and_chat_api(monkeypatch):
    recorded = {}

    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"message": {"content": "My name is Kusma."}}

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, json):
            recorded["url"] = url
            recorded["json"] = json
            return Response()

    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.settings, "OLLAMA_BASE_URL", "http://ollama.local/")
    monkeypatch.setattr(translation_module.settings, "OLLAMA_MODEL", "llama3.2:3b")

    result = await translation_module._call_ollama("मेरा नाम कस्मा है", "hi_to_en")
    assert result == "My name is Kusma."
    assert recorded["url"] == "http://ollama.local/api/chat"
    assert recorded["json"]["model"] == "llama3.2:3b"
    assert recorded["json"]["stream"] is False
    assert "professional Hindi-to-English translator" in recorded["json"]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_ollama_failure_is_not_replaced_with_source_text(monkeypatch):
    async def unavailable(*args, **kwargs): return None
    monkeypatch.setattr(translation_module, "_call_ollama", unavailable)
    with pytest.raises(TranslationError, match="Ensure Ollama is running"):
        await translation_service.translate("Where are you from?", "en", "hi")


@pytest.mark.asyncio
async def test_ollama_requests_are_serialized(monkeypatch):
    active = 0
    maximum_active = 0

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "translated"}}

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return Response()

    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    results = await asyncio.gather(
        translation_module._call_ollama("one", "en_to_hi"),
        translation_module._call_ollama("two", "en_to_hi"),
    )
    assert results == ["translated", "translated"]
    assert maximum_active == 1


@pytest.mark.asyncio
async def test_groq_is_selected_for_deployed_provider(monkeypatch):
    async def groq(text, direction, romanized_hindi=False): return "What's your name?"
    monkeypatch.setattr(translation_module.settings, "TRANSLATION_PROVIDER", "groq")
    monkeypatch.setattr(translation_module, "_call_groq", groq)
    assert await translation_service.translate("आपका नाम क्या है?", "hi", "en") == "What's your name?"


@pytest.mark.asyncio
async def test_groq_uses_configured_model_and_shared_429_cooldown(monkeypatch):
    requests = []
    responses = [
        type("Response", (), {"status_code": 429, "headers": {"Retry-After": "0.25"}})(),
        type("Response", (), {
            "status_code": 200,
            "headers": {},
            "raise_for_status": lambda self: None,
            "json": lambda self: {"choices": [{"message": {"content": "Drink water."}}]},
        })(),
    ]

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, headers, json):
            requests.append((url, headers, json))
            return responses.pop(0)

    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.settings, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(translation_module.settings, "GROQ_MODEL", "qwen/qwen3.8-27b")
    translation_module._GROQ_MIN_INTERVAL_SECONDS = 0

    result = await translation_module._call_groq("पानी पियो", "hi_to_en")
    assert result == "Drink water."
    assert len(requests) == 2
    assert requests[0][0] == "https://api.groq.com/openai/v1/chat/completions"
    assert requests[0][1]["Authorization"] == "Bearer test-key"
    assert requests[0][2]["model"] == "qwen/qwen3.8-27b"


@pytest.mark.asyncio
async def test_groq_requests_are_serialized(monkeypatch):
    active = 0
    maximum_active = 0

    class Response:
        status_code = 200
        headers = {}
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "translated"}}]}

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return Response()

    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.settings, "GROQ_API_KEY", "test-key")
    translation_module._GROQ_MIN_INTERVAL_SECONDS = 0
    results = await asyncio.gather(
        translation_module._call_groq("first", "en_to_hi"),
        translation_module._call_groq("second", "en_to_hi"),
    )
    assert results == ["translated", "translated"]
    assert maximum_active == 1
