import pytest
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
