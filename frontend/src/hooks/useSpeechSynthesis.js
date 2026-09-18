import { useState, useCallback, useEffect, useRef } from 'react';

export function useSpeechSynthesis() {
  const [speakEnabled, setSpeakEnabled] = useState(false);
  const [voices, setVoices] = useState([]);
  const voicesRef = useRef([]);
  const utteranceRef = useRef(null);

  const updateVoices = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      const availableVoices = window.speechSynthesis.getVoices();
      if (availableVoices && availableVoices.length > 0) {
        voicesRef.current = availableVoices;
        setVoices(availableVoices);
      }
    }
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      updateVoices();
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = updateVoices;
      }
    }
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, [updateVoices]);

  const speak = useCallback((text, langCode, isManual = false) => {
    if ((!speakEnabled && !isManual) || !text || typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return;
    }

    try {
      window.speechSynthesis.cancel(); // Stop ongoing speech

      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
      }

      const cleanText = text.trim();
      if (!cleanText) return;

      const utterance = new SpeechSynthesisUtterance(cleanText);

      // Keep reference to prevent Chrome garbage collection mid-speech
      utteranceRef.current = utterance;
      utterance.onend = () => {
        utteranceRef.current = null;
      };
      utterance.onerror = (err) => {
        console.warn('SpeechSynthesis utterance error:', err);
        utteranceRef.current = null;
      };

      // Query latest available voices
      let availableVoices = window.speechSynthesis.getVoices();
      if (!availableVoices || availableVoices.length === 0) {
        availableVoices = voicesRef.current;
      }

      const isHindi = langCode === 'hi';
      let matchingVoice = null;

      if (isHindi) {
        utterance.lang = 'hi-IN';
        matchingVoice =
          availableVoices.find((v) => v.lang.toLowerCase().includes('hi-in')) ||
          availableVoices.find((v) => v.lang.toLowerCase().includes('hi'));
      } else {
        // English target language (en-US or en-IN)
        utterance.lang = 'en-US';
        matchingVoice =
          availableVoices.find((v) => v.lang.toLowerCase().includes('en-us')) ||
          availableVoices.find((v) => v.lang.toLowerCase().includes('en-in')) ||
          availableVoices.find((v) => v.lang.toLowerCase().startsWith('en')) ||
          availableVoices.find((v) => v.lang.toLowerCase().includes('en'));
      }

      if (matchingVoice) {
        utterance.voice = matchingVoice;
        utterance.lang = matchingVoice.lang;
      }

      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.warn('SpeechSynthesis error:', err);
    }
  }, [speakEnabled]);

  return {
    speakEnabled,
    setSpeakEnabled,
    speak,
  };
}

