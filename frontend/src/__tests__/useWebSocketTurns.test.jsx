import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useWebSocket } from '../hooks/useWebSocket';

class MockWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  constructor() {
    this.readyState = MockWebSocket.CONNECTING;
    MockWebSocket.instance = this;
  }
  close() { this.readyState = 3; }
  send() {}
  message(data) { this.onmessage?.({ data: JSON.stringify(data) }); }
}

describe('WebSocket conversation turn updates', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('updates the existing conversation message by TURN_ID', () => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    const { result, unmount } = renderHook(() => useWebSocket());
    const socket = MockWebSocket.instance;
    act(() => socket.message({
      type: 'final', turn_id: 'turn-1', speaker: 'person_a', original_text: 'नमस्ते',
      translation_status: 'pending', translated_text: '',
    }));
    act(() => socket.message({
      type: 'final', turn_id: 'turn-1', speaker: 'person_a', original_text: 'नमस्ते',
      translation_status: 'translated', translated_text: 'Hello.',
    }));
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({ id: 'turn-1', translation_status: 'translated', translation: 'Hello.' });
    unmount();
  });
});
