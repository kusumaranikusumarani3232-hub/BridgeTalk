import { useState, useCallback, useEffect, useRef } from 'react';

export function useSpeechSynthesis() {
  const [speakEnabled, setSpeakEnabled] = useState(false);
  const [voices, setVoices] = useState([]);
  const voicesRef = useRef([]);
  const utteranceRef = useRef([]);
  const speechIdRef = useRef(0);

  const updateVoices = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      const availableVoices = window.speechSynthesis.getVoices();

      if (availableVoices.length > 0) {
        voicesRef.current = availableVoices;
        setVoices(availableVoices);
      }
    }
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      updateVoices();

      window.speechSynthesis.onvoiceschanged = updateVoices;
    }

    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, [updateVoices]);

  const speak = useCallback(
    (text, langCode, isManual = false) => {
      if (
        (!speakEnabled && !isManual) ||
        !text ||
        typeof window === 'undefined' ||
        !('speechSynthesis' in window)
      ) {
        return;
      }

      const cleanText = String(text).trim();
      if (!cleanText) return;

      const speech = window.speechSynthesis;

      // Invalidate any previously scheduled speech timeout
      speechIdRef.current += 1;
      const currentSpeechId = speechIdRef.current;

      // Cancel any current speech in Chrome queue
      speech.cancel();

      let availableVoices = speech.getVoices();
      if (!availableVoices.length) {
        availableVoices = voicesRef.current;
      }

      const langLower = String(langCode || '').toLowerCase();
      const isHindi =
        langLower.includes('hindi') || langLower.startsWith('hi');

      let matchingVoice;
      if (isHindi) {
        matchingVoice =
          availableVoices.find(
            (voice) =>
              voice.name === 'Google हिन्दी' &&
              voice.lang.toLowerCase().includes('hi')
          ) ||
          availableVoices.find(
            (voice) => voice.name === 'Google हिन्दी'
          ) ||
          availableVoices.find(
            (voice) =>
              voice.name.includes('Google') &&
              voice.lang.toLowerCase().includes('hi')
          ) ||
          availableVoices.find((voice) =>
            voice.lang.toLowerCase().includes('hi')
          );
      } else {
        matchingVoice =
          availableVoices.find(
            (voice) => voice.lang.toLowerCase() === 'en-us'
          ) ||
          availableVoices.find(
            (voice) => voice.lang.toLowerCase() === 'en-in'
          ) ||
          availableVoices.find((voice) =>
            voice.lang.toLowerCase().startsWith('en')
          );
      }

      const utterance = new SpeechSynthesisUtterance(cleanText);

      utterance.lang = matchingVoice
        ? matchingVoice.lang
        : isHindi
          ? 'hi-IN'
          : 'en-US';

      if (matchingVoice) {
        utterance.voice = matchingVoice;
      }

      utterance.rate = isHindi ? 0.8 : 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;

      utterance.onstart = () => {
        console.log('🔊 TTS playback started:', {
          lang: utterance.lang,
          voice: matchingVoice?.name || 'default',
          text: cleanText,
        });
      };

      utterance.onend = () => {
        console.log('🔊 TTS playback completed:', cleanText);
      };

      utterance.onerror = (event) => {
        console.warn('🔊 SpeechSynthesis error event:', {
          error: event.error,
          language: utterance.lang,
          voice: matchingVoice?.name,
          text: cleanText,
        });
      };

      // Keep utterance in ref to prevent Chrome garbage collection
      utteranceRef.current = [utterance];

      // Allow 250ms after cancel() for browser speech queue to settle
      setTimeout(() => {
        if (currentSpeechId === speechIdRef.current) {
          speech.speak(utterance);
        }
      }, 250);
    },
    [speakEnabled]
  );

  return {
    speakEnabled,
    setSpeakEnabled,
    speak,
  };
}


