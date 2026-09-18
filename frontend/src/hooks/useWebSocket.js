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

      // Cancel the previous complete speech sequence.
      speechIdRef.current += 1;
      const currentSpeechId = speechIdRef.current;

      speech.cancel();

      let availableVoices = speech.getVoices();

      if (!availableVoices.length) {
        availableVoices = voicesRef.current;
      }

      const isHindi =
        String(langCode || '').toLowerCase().startsWith('hi');

      let matchingVoice;

      if (isHindi) {
        matchingVoice =
          availableVoices.find(
            (voice) =>
              voice.name === 'Google हिन्दी' &&
              voice.lang.toLowerCase() === 'hi-in'
          ) ||
          availableVoices.find(
            (voice) => voice.lang.toLowerCase() === 'hi-in'
          ) ||
          availableVoices.find(
            (voice) => voice.lang.toLowerCase().startsWith('hi')
          );
      } else {
        matchingVoice =
          availableVoices.find(
            (voice) => voice.lang.toLowerCase() === 'en-us'
          ) ||
          availableVoices.find(
            (voice) => voice.lang.toLowerCase() === 'en-in'
          ) ||
          availableVoices.find(
            (voice) => voice.lang.toLowerCase().startsWith('en')
          );
      }

      /*
       * Hindi Chrome TTS can stop on longer utterances.
       * Keep each utterance short (about 6-8 words).
       */
      const words = cleanText.split(/\s+/);
      const chunks = [];

      if (isHindi && words.length > 8) {
        for (let i = 0; i < words.length; i += 7) {
          chunks.push(words.slice(i, i + 7).join(' '));
        }
      } else {
        chunks.push(cleanText);
      }

      utteranceRef.current = [];

      const speakChunk = (index) => {
        if (currentSpeechId !== speechIdRef.current) {
          return;
        }

        if (index >= chunks.length) {
          utteranceRef.current = [];
          return;
        }

        const utterance = new SpeechSynthesisUtterance(chunks[index]);

        utterance.lang = matchingVoice
          ? matchingVoice.lang
          : isHindi
            ? 'hi-IN'
            : 'en-US';

        if (matchingVoice) {
          utterance.voice = matchingVoice;
        }

        // Slightly slower for Hindi clarity.
        utterance.rate = isHindi ? 0.9 : 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        utterance.onend = () => {
          if (currentSpeechId !== speechIdRef.current) {
            return;
          }

          setTimeout(() => {
            speakChunk(index + 1);
          }, 120);
        };

        utterance.onerror = (event) => {
          console.warn('SpeechSynthesis error:', {
            error: event.error,
            language: utterance.lang,
            voice: matchingVoice?.name,
            text: chunks[index],
          });

          if (currentSpeechId === speechIdRef.current) {
            utteranceRef.current = [];
          }
        };

        // Keep every utterance alive.
        utteranceRef.current.push(utterance);

        speech.speak(utterance);
      };

      // Start after cancel() has finished clearing Chrome's queue.
      setTimeout(() => {
        if (currentSpeechId === speechIdRef.current) {
          speakChunk(0);
        }
      }, 100);
    },
    [speakEnabled]
  );

  return {
    speakEnabled,
    setSpeakEnabled,
    speak,
  };
}

