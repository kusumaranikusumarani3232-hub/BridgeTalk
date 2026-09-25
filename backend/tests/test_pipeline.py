import asyncio
import json

import pytest

from app.websocket import WebSocketHandler
from app import websocket as websocket_module


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_text(self, payload):
        self.sent.append(json.loads(payload))


@pytest.mark.asyncio
async def test_final_turns_are_unique_ordered_and_keep_speaker(monkeypatch):
    async def translate(text, source_lang, target_lang):
        await asyncio.sleep(0.005)
        return f"{target_lang}:{text}"

    monkeypatch.setattr(websocket_module.translation_service, "translate", translate)
    handler = WebSocketHandler(FakeWebSocket())
    hindi_turns = ["नमस्ते", "आप कैसे हैं?", "समय क्या हुआ है?", "आज मौसम कैसा है?", "मेरा नाम कुसुमा है।"]
    english_turns = ["Hello", "Good morning", "I'm doing well, thank you.", "How are you?", "What's your name?"]

    for order, text in enumerate(hindi_turns):
        await handler.on_final_transcript(text, "person_a", {"turn_order": order})
    for order, text in enumerate(english_turns):
        await handler.on_final_transcript(text, "person_b", {"turn_order": order})
    await handler.on_final_transcript("नमस्ते", "person_a", {"turn_order": 0})  # provider retry
    await handler.translation_queue.join()

    messages = handler.websocket.sent
    assert len(messages) == 10
    assert len({message["id"] for message in messages}) == 10
    assert [message["speaker"] for message in messages] == ["person_a"] * 5 + ["person_b"] * 5
    assert [message["original_text"] for message in messages] == hindi_turns + english_turns
    assert all(message["translation_status"] == "translated" for message in messages)
    assert all(message["translation"] != message["original_text"] for message in messages)
    handler.translation_worker.cancel()
    await asyncio.gather(handler.translation_worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_speaker_switch_sequence_and_translation_failure(monkeypatch):
    async def translate(text, source_lang, target_lang):
        if text == "fail me":
            raise RuntimeError("provider unavailable")
        return f"{target_lang}:{text}"

    monkeypatch.setattr(websocket_module.translation_service, "translate", translate)
    handler = WebSocketHandler(FakeWebSocket())
    sequence = [("person_a", "आप कैसे हैं?"), ("person_b", "Hello"), ("person_a", "समय क्या हुआ है?"), ("person_b", "Thank you")]
    for i, (speaker, text) in enumerate(sequence):
        await handler.on_final_transcript(text, speaker, {"turn_order": i})
    await handler.on_final_transcript("fail me", "person_b", {"turn_order": 5})
    await handler.translation_queue.join()

    messages = handler.websocket.sent
    assert [item["speaker"] for item in messages] == [speaker for speaker, _ in sequence] + ["person_b"]
    failed = messages[-1]
    assert failed["translation_status"] == "failed"
    assert failed["translation"] == ""
    assert failed["translation"] != failed["original_text"]
    handler.translation_worker.cancel()
    await asyncio.gather(handler.translation_worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_duplicate_final_is_not_translated_and_queue_is_bounded(monkeypatch):
    entered = asyncio.Event()
    release = asyncio.Event()
    translated = []
    active = 0
    max_active = 0

    async def translate(text, source_lang, target_lang):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        translated.append(text)
        entered.set()
        await release.wait()
        active -= 1
        return f"{target_lang}:{text}"

    monkeypatch.setattr(websocket_module.translation_service, "translate", translate)
    handler = WebSocketHandler(FakeWebSocket())
    await handler.on_final_transcript("first", "person_b", {"turn_order": 1})
    await entered.wait()
    for order in range(2, 18):
        await handler.on_final_transcript(f"turn-{order}", "person_b", {"turn_order": order})
    await handler.on_final_transcript("overflow", "person_b", {"turn_order": 18})
    await handler.on_final_transcript("first", "person_b", {"turn_order": 1})
    release.set()
    await handler.translation_queue.join()

    assert translated == ["first"] + [f"turn-{order}" for order in range(2, 18)]
    assert max_active == 1
    assert [message["original_text"] for message in handler.websocket.sent] == ["overflow"] + translated
    assert handler.websocket.sent[0]["translation_status"] == "failed"
    handler.translation_worker.cancel()
    await asyncio.gather(handler.translation_worker, return_exceptions=True)
