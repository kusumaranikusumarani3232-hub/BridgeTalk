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

      try {
        const cleanText = text.trim();

        if (!cleanText) return;

        window.speechSynthesis.cancel();

        if (window.speechSynthesis.paused) {
          window.speechSynthesis.resume();
        }

        let availableVoices = window.speechSynthesis.getVoices();

        if (!availableVoices || availableVoices.length === 0) {
          availableVoices = voicesRef.current;
        }

        const isHindi = langCode === 'hi';

        let matchingVoice = null;

        if (isHindi) {
          // Explicitly prefer Google's Hindi voice.
          matchingVoice =
            availableVoices.find(
              (v) =>
                v.name === 'Google हिन्दी' &&
                v.lang.toLowerCase() === 'hi-in'
            ) ||
            availableVoices.find(
              (v) => v.lang.toLowerCase() === 'hi-in'
            ) ||
            availableVoices.find(
              (v) => v.lang.toLowerCase().startsWith('hi')
            );
        } else {
          matchingVoice =
            availableVoices.find(
              (v) => v.lang.toLowerCase() === 'en-us'
            ) ||
            availableVoices.find(
              (v) => v.lang.toLowerCase() === 'en-in'
            ) ||
            availableVoices.find(
              (v) => v.lang.toLowerCase().startsWith('en')
            );
        }

        // Hindi works more reliably when spoken in short chunks.
        const chunks = isHindi
          ? cleanText
              .split(/(?<=[।!?])\s+|(?<=[.!?])\s+/)
              .map((chunk) => chunk.trim())
              .filter(Boolean)
          : [cleanText];

        let chunkIndex = 0;

        const speakNextChunk = () => {
          if (chunkIndex >= chunks.length) {
            utteranceRef.current = null;
            return;
          }

          const utterance = new SpeechSynthesisUtterance(
            chunks[chunkIndex]
          );

          utteranceRef.current = utterance;

          if (matchingVoice) {
            utterance.voice = matchingVoice;
            utterance.lang = matchingVoice.lang;
          } else {
            utterance.lang = isHindi ? 'hi-IN' : 'en-US';
          }

          utterance.rate = 0.95;
          utterance.pitch = 1.0;

          utterance.onend = () => {
            chunkIndex += 1;

            // Give Chrome a tiny gap between Hindi chunks.
            setTimeout(speakNextChunk, isHindi ? 80 : 0);
          };

          utterance.onerror = (err) => {
            console.warn('SpeechSynthesis utterance error:', err);
            utteranceRef.current = null;
          };

          window.speechSynthesis.speak(utterance);
        };

        speakNextChunk();
      } catch (err) {
        console.warn('SpeechSynthesis error:', err);
      }
    },
    [speakEnabled]
  );

  return {
    speakEnabled,
    setSpeakEnabled,
    speak,
  };
}
```
