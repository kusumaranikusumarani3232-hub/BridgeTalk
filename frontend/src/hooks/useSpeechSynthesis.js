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

      // Invalidate any previously scheduled speech sequence
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

      // Hindi Chrome TTS fails/stops on long text payloads.
      // Break long Hindi text into short ~6-word chunks to prevent Chrome TTS silent failures.
      const words = cleanText.split(/\s+/);
      const chunks = [];

      if (isHindi && words.length > 7) {
        for (let i = 0; i < words.length; i += 6) {
          chunks.push(words.slice(i, i + 6).join(' '));
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

        utterance.rate = isHindi ? 0.85 : 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        utterance.onstart = () => {
          console.log('🔊 TTS playback started chunk:', {
            index,
            totalChunks: chunks.length,
            lang: utterance.lang,
            voice: matchingVoice?.name || 'default',
            text: chunks[index],
          });
        };

        utterance.onend = () => {
          if (currentSpeechId !== speechIdRef.current) {
            return;
          }
          console.log(`🔊 TTS chunk ${index + 1}/${chunks.length} completed.`);
          setTimeout(() => {
            speakChunk(index + 1);
          }, 100);
        };

        utterance.onerror = (event) => {
          console.warn('🔊 SpeechSynthesis error event:', {
            error: event.error,
            language: utterance.lang,
            voice: matchingVoice?.name,
            text: chunks[index],
          });
          if (currentSpeechId === speechIdRef.current) {
            utteranceRef.current = [];
          }
        };

        // Keep active utterances in ref to prevent Chrome garbage collection mid-speech
        utteranceRef.current.push(utterance);

        speech.speak(utterance);
      };

      // Allow 200ms after cancel() for browser speech queue to settle before starting chunk sequence
      setTimeout(() => {
        if (currentSpeechId === speechIdRef.current) {
          speakChunk(0);
        }
      }, 200);
    },
    [speakEnabled]
  );

  return {
    speakEnabled,
    setSpeakEnabled,
    speak,
  };
}
