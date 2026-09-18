import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSpeechSynthesis } from '../hooks/useSpeechSynthesis';

describe('useSpeechSynthesis hook unit tests', () => {
  let mockSpeakFn;
  let mockCancelFn;
  let mockGetVoicesFn;
  let createdUtterances = [];

  beforeEach(() => {
    createdUtterances = [];
    mockSpeakFn = vi.fn((utterance) => {
      // Simulate onend after a short timer
    });
    mockCancelFn = vi.fn();
    mockGetVoicesFn = vi.fn().mockReturnValue([
      { name: 'Google हिन्दी', lang: 'hi-IN' },
      { name: 'Google US English', lang: 'en-US' },
    ]);

    // Mock window.SpeechSynthesisUtterance
    global.SpeechSynthesisUtterance = class {
      constructor(text) {
        this.text = text;
        this.lang = '';
        this.voice = null;
        this.rate = 1.0;
        this.pitch = 1.0;
        this.volume = 1.0;
        this.onend = null;
        this.onerror = null;
        this.onstart = null;
        createdUtterances.push(this);
      }
    };

    // Mock window.speechSynthesis
    Object.defineProperty(window, 'speechSynthesis', {
      value: {
        getVoices: mockGetVoicesFn,
        cancel: mockCancelFn,
        speak: mockSpeakFn,
        onvoiceschanged: null,
      },
      writable: true,
      configurable: true,
    });

    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('does not speak when speakEnabled is false and isManual is false', () => {
    const { result } = renderHook(() => useSpeechSynthesis());
    act(() => {
      result.current.speak('क्या हम कल सुबह दस बजे मीटिंग कर सकते हैं', 'hi');
    });

    vi.advanceTimersByTime(300);
    expect(mockSpeakFn).not.toHaveBeenCalled();
  });

  it('speaks short Hindi text ("नमस्ते") in a single utterance', () => {
    const { result } = renderHook(() => useSpeechSynthesis());

    act(() => {
      result.current.setSpeakEnabled(true);
    });

    act(() => {
      result.current.speak('नमस्ते', 'hi');
    });

    expect(mockCancelFn).toHaveBeenCalled();
    vi.advanceTimersByTime(250);

    expect(mockSpeakFn).toHaveBeenCalledTimes(1);
    expect(createdUtterances.length).toBe(1);
    expect(createdUtterances[0].text).toBe('नमस्ते');
    expect(createdUtterances[0].lang).toBe('hi-IN');
    expect(createdUtterances[0].voice.name).toBe('Google हिन्दी');
    expect(createdUtterances[0].rate).toBe(0.85);
  });

  it('chunks long Hindi text into multiple short utterances played sequentially', () => {
    const { result } = renderHook(() => useSpeechSynthesis());

    act(() => {
      result.current.setSpeakEnabled(true);
    });

    // 8 words > 7 words threshold
    const longHindiText = 'क्या हम कल सुबह दस बजे मीटिंग कर सकते हैं';

    act(() => {
      result.current.speak(longHindiText, 'hi');
    });

    expect(mockCancelFn).toHaveBeenCalled();
    vi.advanceTimersByTime(250);

    // First chunk spoken
    expect(mockSpeakFn).toHaveBeenCalledTimes(1);
    expect(createdUtterances.length).toBe(1);
    expect(createdUtterances[0].text).toBe('क्या हम कल सुबह दस बजे');
    expect(createdUtterances[0].lang).toBe('hi-IN');

    // Simulate first chunk ending
    act(() => {
      if (createdUtterances[0].onend) {
        createdUtterances[0].onend();
      }
    });
    vi.advanceTimersByTime(150);

    // Second chunk spoken
    expect(mockSpeakFn).toHaveBeenCalledTimes(2);
    expect(createdUtterances.length).toBe(2);
    expect(createdUtterances[1].text).toBe('मीटिंग कर सकते हैं');
  });

  it('speaks English sentence with en-US voice and rate 1.0', () => {
    const { result } = renderHook(() => useSpeechSynthesis());

    act(() => {
      result.current.setSpeakEnabled(true);
    });

    const englishText = 'Hello, can we meet tomorrow at ten o clock?';

    act(() => {
      result.current.speak(englishText, 'en');
    });

    vi.advanceTimersByTime(250);

    expect(mockSpeakFn).toHaveBeenCalledTimes(1);
    expect(createdUtterances[0].text).toBe(englishText);
    expect(createdUtterances[0].lang).toBe('en-US');
    expect(createdUtterances[0].voice.name).toBe('Google US English');
    expect(createdUtterances[0].rate).toBe(1.0);
  });
});
