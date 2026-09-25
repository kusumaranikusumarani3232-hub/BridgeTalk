import { describe, expect, it } from 'vitest';
import { getWebSocketUrl } from '../hooks/useWebSocket';

describe('WebSocket endpoint selection', () => {
  it('uses the local backend for local development', () => {
    expect(getWebSocketUrl('localhost', true)).toBe('ws://localhost:8000/ws/transcribe');
  });

  it('keeps the Render endpoint for production', () => {
    expect(getWebSocketUrl('bridgetalk.example.com', false)).toBe('wss://bridgetalk-olvd.onrender.com/ws/transcribe');
  });
});
