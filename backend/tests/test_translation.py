import pytest
from app import translation_service as translation_module
from app.translation_service import translation_service

@pytest.mark.asyncio
async def test_same_language_translation():
    res = await translation_service.translate("Hello world", "en", "en")
    assert res == "Hello world"

@pytest.mark.asyncio
async def test_empty_translation():
    res = await translation_service.translate("", "hi", "en")
    assert res == ""

@pytest.mark.asyncio
async def test_translation_fallback_or_service():
    # Test English to Hindi or fallback
    res = await translation_service.translate("Hello", "en", "hi")
    assert isinstance(res, str)
    assert len(res) > 0


@pytest.mark.asyncio
async def test_okay_is_translated_instead_of_rendering_ellipsis():
    english_to_hindi = await translation_service.translate("Okay.", "en", "hi")
    hindi_to_english = await translation_service.translate("Okay.", "hi", "en")

    assert english_to_hindi == "ठीक है।"
    assert hindi_to_english == "Okay."


@pytest.mark.asyncio
async def test_translation_gateway_retries_transient_server_failure(monkeypatch):
    responses = [
        type("Response", (), {"status_code": 503, "headers": {}, "json": lambda self: {}})(),
        type("Response", (), {"status_code": 200, "headers": {}, "json": lambda self: {
            "choices": [{"message": {"content": "सुप्रभात।"}}],
            "request_id": "test-request",
        }})(),
    ]
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            calls.append(1)
            return responses.pop(0)

    async def no_wait(_):
        return None

    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.asyncio, "sleep", no_wait)
    monkeypatch.setattr(translation_module.settings, "ASSEMBLYAI_API_KEY", "test-api-key")

    result = await translation_module._call_llm_gateway("Good morning", "en_to_hi")

    assert result == "सुप्रभात।"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_rate_limit_retries_are_bounded_and_fast(monkeypatch):
    calls = []
    waits = []

    class Response:
        status_code = 429
        headers = {}

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            calls.append(1)
            return Response()

    async def record_wait(delay): waits.append(delay)
    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.asyncio, "sleep", record_wait)
    monkeypatch.setattr(translation_module.settings, "ASSEMBLYAI_API_KEY", "test-api-key")

    result = await translation_module._call_llm_gateway("A fresh sentence", "en_to_hi")

    assert result is None
    assert len(calls) == translation_module._MAX_GATEWAY_ATTEMPTS
    assert len(waits) == translation_module._MAX_GATEWAY_ATTEMPTS - 1
    assert sum(waits) <= 1.5


@pytest.mark.asyncio
async def test_retry_after_is_capped(monkeypatch):
    calls = []
    waits = []

    class Response:
        status_code = 429
        headers = {"Retry-After": "30"}

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            calls.append(1)
            return Response()

    async def record_wait(delay): waits.append(delay)
    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.asyncio, "sleep", record_wait)
    monkeypatch.setattr(translation_module.settings, "ASSEMBLYAI_API_KEY", "test-api-key")

    assert await translation_module._call_llm_gateway("A fresh sentence", "en_to_hi") is None
    assert waits == [translation_module._MAX_RETRY_AFTER_SECONDS] * 2
    assert len(calls) == translation_module._MAX_GATEWAY_ATTEMPTS


@pytest.mark.asyncio
async def test_gateway_http_200_translation_unchanged(monkeypatch):
    class Response:
        status_code = 200
        headers = {}
        def json(self):
            return {"choices": [{"message": {"content": "यह एक परीक्षण है।"}}]}

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs): return Response()

    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.settings, "ASSEMBLYAI_API_KEY", "test-api-key")
    assert await translation_service.translate("This is a test", "en", "hi") == "यह एक परीक्षण है।"
