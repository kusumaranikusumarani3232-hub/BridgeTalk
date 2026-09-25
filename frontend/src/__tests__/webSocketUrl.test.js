import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { getWebSocketUrl, useWebSocket } from '../hooks/useWebSocket';

describe('WebSocket endpoint selection', () => {
  it('uses the local backend for local development', () => {
    expect(getWebSocketUrl('localhost', true)).toBe('ws://localhost:8000/ws/transcribe');
  });

  it('keeps the Render endpoint for production', () => {
    expect(getWebSocketUrl('bridgetalk.example.com', false)).toBe('wss://bridgetalk-olvd.onrender.com/ws/transcribe');
  });

  it('updates an existing final message when its TURN_ID gets a translation', () => {
    let socket;
    class FakeWebSocket {
      static OPEN = 1;
      static CONNECTING = 0;
      constructor() {
        this.readyState = FakeWebSocket.CONNECTING;
        socket = this;
      }
      close() { this.readyState = 3; }
    }
    const originalWebSocket = window.WebSocket;
    window.WebSocket = FakeWebSocket;
    const { result, unmount } = renderHook(() => useWebSocket());

    act(() => socket.onmessage({ data: JSON.stringify({
      type: 'final', id: 'turn-1', speaker: 'person_b', speaker_name: 'Person B',
      source_language: 'English', target_language: 'Hindi', original_text: 'Hello',
      translation: '', translation_status: 'pending',
    }) }));
    act(() => socket.onmessage({ data: JSON.stringify({
      type: 'final', id: 'turn-1', speaker: 'person_b', speaker_name: 'Person B',
      source_language: 'English', target_language: 'Hindi', original_text: 'Hello',
      translation: 'नमस्ते', translation_status: 'translated',
    }) }));

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].id).toBe('turn-1');
    expect(result.current.messages[0].translation).toBe('नमस्ते');
    expect(result.current.messages[0].translation_status).toBe('translated');

    unmount();
    window.WebSocket = originalWebSocket;
  });
});
