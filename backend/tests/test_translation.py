import asyncio
import pytest
from app import translation_service as translation_module
from app.translation_service import translation_service


@pytest.fixture(autouse=True)
def reset_gateway_state():
    translation_module._gateway_cooldown_until = 0
    translation_module._gateway_next_request_at = 0


@pytest.mark.asyncio
async def test_same_language_translation():
    res = await translation_service.translate("Hello world", "en", "en")
    assert res == "Hello world"

@pytest.mark.asyncio
async def test_empty_translation():
    res = await translation_service.translate("", "hi", "en")
    assert res == ""

@pytest.mark.asyncio
async def test_translation_uses_gateway_result(monkeypatch):
    async def gateway(text, direction, romanized_hindi=False): return "नमस्ते"
    monkeypatch.setattr(translation_module, "_call_llm_gateway", gateway)
    res = await translation_service.translate("Hello", "en", "hi")
    assert res == "नमस्ते"


@pytest.mark.asyncio
async def test_both_directions_use_gateway(monkeypatch):
    async def gateway(text, direction, romanized_hindi=False):
        return "ठीक है।" if direction == "en_to_hi" else "Okay."
    monkeypatch.setattr(translation_module, "_call_llm_gateway", gateway)
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
async def test_cooldown_serializes_requests_and_honors_retry_after(monkeypatch):
    calls = []

    class Response:
        status_code = 429
        headers = {"Retry-After": "0.25"}

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            calls.append(1)
            return Response()

    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.settings, "ASSEMBLYAI_API_KEY", "test-api-key")

    loop = asyncio.get_running_loop()
    translation_module._gateway_cooldown_until = 0
    translation_module._gateway_next_request_at = 0
    result = await translation_module._call_llm_gateway("A fresh sentence", "en_to_hi")
    skipped = await translation_module._call_llm_gateway("Another sentence", "en_to_hi")

    assert result is None
    assert skipped is None
    assert len(calls) == 2
    assert translation_module._gateway_cooldown_until > loop.time()


@pytest.mark.asyncio
async def test_retry_after_is_capped(monkeypatch):
    calls = []

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

    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.settings, "ASSEMBLYAI_API_KEY", "test-api-key")
    translation_module._gateway_cooldown_until = 0
    translation_module._gateway_next_request_at = 0

    assert await translation_module._call_llm_gateway("A fresh sentence", "en_to_hi") is None
    assert translation_module._gateway_cooldown_until - asyncio.get_running_loop().time() <= translation_module._MAX_RETRY_AFTER_SECONDS
    assert translation_module._gateway_cooldown_until - asyncio.get_running_loop().time() >= translation_module._MAX_RETRY_AFTER_SECONDS - 0.1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_successful_200_resets_cooldown(monkeypatch):
    calls = []
    responses = [
        type("Response", (), {"status_code": 429, "headers": {"Retry-After": "0.25"}, "json": lambda self: {}})(),
        type("Response", (), {"status_code": 200, "headers": {}, "json": lambda self: {"choices": [{"message": {"content": "नमस्ते"}}]}})(),
    ]

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            calls.append(1)
            return responses.pop(0)

    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.settings, "ASSEMBLYAI_API_KEY", "test-api-key")
    translation_module._gateway_cooldown_until = 0
    translation_module._gateway_next_request_at = 0

    assert await translation_module._call_llm_gateway("Hello there", "en_to_hi") is None
    assert await translation_module._call_llm_gateway("Hello there", "en_to_hi") == "नमस्ते"
    assert translation_module._gateway_cooldown_until == 0
    assert len(calls) == 2


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
    translation_module._gateway_cooldown_until = 0
    translation_module._gateway_next_request_at = 0
    assert await translation_service.translate("This is a test", "en", "hi") == "यह एक परीक्षण है।"


@pytest.mark.asyncio
async def test_gateway_requests_remain_spaced_after_cooldown(monkeypatch):
    request_times = []
    loop = asyncio.get_running_loop()

    class Response:
        status_code = 200
        headers = {}
        def json(self):
            return {"choices": [{"message": {"content": "नमस्ते"}}]}

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            request_times.append(asyncio.get_running_loop().time())
            return Response()

    monkeypatch.setattr(translation_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(translation_module.settings, "ASSEMBLYAI_API_KEY", "test-api-key")
    translation_module._gateway_cooldown_until = loop.time() + 1
    translation_module._gateway_next_request_at = 0

    assert await translation_module._call_llm_gateway("during cooldown", "en_to_hi") == "नमस्ते"
    assert await translation_module._call_llm_gateway("first", "en_to_hi") == "नमस्ते"
    assert await translation_module._call_llm_gateway("second", "en_to_hi") == "नमस्ते"
    assert request_times[1] - request_times[0] >= translation_module._MIN_GATEWAY_REQUEST_INTERVAL * 0.8


@pytest.mark.asyncio
async def test_gateway_never_has_concurrent_requests(monkeypatch):
    active = 0
    maximum_active = 0

    class Response:
        status_code = 200
        headers = {}
        def json(self):
            return {"choices": [{"message": {"content": "translated"}}]}

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
    monkeypatch.setattr(translation_module.settings, "ASSEMBLYAI_API_KEY", "test-api-key")
    translation_module._gateway_cooldown_until = 0
    translation_module._gateway_next_request_at = 0
    results = await asyncio.gather(
        translation_module._call_llm_gateway("first", "en_to_hi"),
        translation_module._call_llm_gateway("second", "en_to_hi"),
    )
    assert results == ["translated", "translated"]
    assert maximum_active == 1
