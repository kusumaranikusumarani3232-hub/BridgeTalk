import React from 'react';
import { act, render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  state: null,
  speak: vi.fn(),
}));

vi.mock('../hooks/useWebSocket', () => ({ useWebSocket: () => mocks.state }));
vi.mock('../hooks/useAudioRecorder', () => ({
  useAudioRecorder: () => ({
    isRecording: false,
    permissionError: null,
    startRecording: vi.fn(),
    stopRecording: vi.fn(),
  }),
}));
vi.mock('../hooks/useSpeechSynthesis', () => ({
  useSpeechSynthesis: () => ({
    speakEnabled: true,
    setSpeakEnabled: vi.fn(),
    speak: mocks.speak,
  }),
}));

import App from '../App';

function emptyState() {
  return {
    isConnected: true,
    assemblyaiReady: true,
    statusMessage: 'Ready',
    partialTranscript: null,
    messages: [],
    insights: [],
    activeSpeaker: 'person_a',
    setActiveSpeaker: vi.fn(),
    sendAction: vi.fn(),
    sendAudioChunk: vi.fn(),
    clearConversation: vi.fn(),
  };
}

function turn(id, { status = 'translated', translation = 'नमस्ते', target = 'Hindi', text = 'same source' } = {}) {
  return {
    id,
    speaker: 'person_a',
    speaker_name: 'Person A',
    source_language: 'English',
    target_language: target,
    original_text: text,
    translation,
    translation_status: status,
  };
}

describe('App TTS after asynchronous translation updates', () => {
  beforeEach(() => {
    mocks.state = emptyState();
    mocks.speak.mockClear();
  });

  it('speaks the final translation when a pending turn is updated', () => {
    const view = render(<App />);
    act(() => {
      mocks.state.messages = [turn('turn-1', { status: 'pending', translation: '' })];
      view.rerender(<App />);
    });
    expect(mocks.speak).not.toHaveBeenCalled();

    act(() => {
      mocks.state.messages = [turn('turn-1', { translation: 'नमस्ते, आप कैसे हैं?' })];
      view.rerender(<App />);
    });
    expect(mocks.speak).toHaveBeenCalledTimes(1);
    expect(mocks.speak).toHaveBeenCalledWith('नमस्ते, आप कैसे हैं?', 'hi');
  });

  it('speaks a translated TURN_ID exactly once across repeated updates', () => {
    const view = render(<App />);
    act(() => {
      mocks.state.messages = [turn('turn-2', { target: 'English', translation: 'Hello there.' })];
      view.rerender(<App />);
    });
    act(() => {
      mocks.state.messages = [turn('turn-2', { target: 'English', translation: 'Hello there again.' })];
      view.rerender(<App />);
    });
    expect(mocks.speak).toHaveBeenCalledTimes(1);
    expect(mocks.speak).toHaveBeenCalledWith('Hello there.', 'en');
  });

  it('does not speak failed or empty translations', () => {
    const view = render(<App />);
    act(() => {
      mocks.state.messages = [
        turn('failed', { status: 'failed', translation: 'No translation' }),
        turn('empty', { translation: '' }),
        turn('null', { translation: null }),
        turn('dots', { translation: '...' }),
        turn('ellipsis', { translation: '…' }),
      ];
      view.rerender(<App />);
    });
    expect(mocks.speak).not.toHaveBeenCalled();
  });

  it('speaks identical text for two distinct turn IDs', () => {
    const view = render(<App />);
    act(() => {
      mocks.state.messages = [
        turn('turn-a', { target: 'English', translation: 'Drink water.', text: 'Drink water.' }),
        turn('turn-b', { target: 'English', translation: 'Drink water.', text: 'Drink water.' }),
      ];
      view.rerender(<App />);
    });
    expect(mocks.speak).toHaveBeenCalledTimes(2);
    expect(mocks.speak).toHaveBeenNthCalledWith(1, 'Drink water.', 'en');
    expect(mocks.speak).toHaveBeenNthCalledWith(2, 'Drink water.', 'en');
  });

  it('routes both Hindi and English translations to the TTS queue', () => {
    const view = render(<App />);
    act(() => {
      mocks.state.messages = [
        turn('hindi', { target: 'Hindi', translation: 'नमस्ते।' }),
        turn('english', { target: 'English', translation: 'Hello.' }),
      ];
      view.rerender(<App />);
    });
    expect(mocks.speak).toHaveBeenNthCalledWith(1, 'नमस्ते।', 'hi');
    expect(mocks.speak).toHaveBeenNthCalledWith(2, 'Hello.', 'en');
  });
});
