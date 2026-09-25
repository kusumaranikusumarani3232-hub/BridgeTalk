import { useState, useCallback, useEffect, useRef } from 'react';

export function useSpeechSynthesis() {
  const [speakEnabled, setSpeakEnabled] = useState(false);
  const [voices, setVoices] = useState([]);
  const voicesRef = useRef([]);
  const utteranceRef = useRef([]);
  const queueRef = useRef([]);
  const speakingRef = useRef(false);
  const speakRef = useRef(null);

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
        queueRef.current = [];
        speakingRef.current = false;
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

      let availableVoices = speech.getVoices();
      if (!availableVoices.length) {
        availableVoices = voicesRef.current;
      }

      // లాంగ్వేజ్ చెకింగ్ - హిందీని మరింత పక్కాగా గుర్తించడానికి
      const langLower = String(langCode || '').toLowerCase();
      const isHindi =
        langLower.includes('hindi') ||
        langLower.startsWith('hi') ||
        /[\u0900-\u097F]/.test(cleanText); // హిందీ అక్షరాలు (Devanagari) ఉంటే ఆటోమేటిక్‌గా ట్రూ అవుతుంది

      let matchingVoice;
      if (isHindi) {
        matchingVoice =
          availableVoices.find(
            (voice) =>
              (voice.name.includes('Google') || voice.name.includes('Microsoft')) &&
              voice.lang.toLowerCase().includes('hi')
          ) ||
          availableVoices.find((voice) =>
            voice.lang.toLowerCase().startsWith('hi')
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

      // వాయిస్ సెట్టింగ్స్
      utterance.lang = matchingVoice ? matchingVoice.lang : (isHindi ? 'hi-IN' : 'en-US');
      if (matchingVoice) {
        utterance.voice = matchingVoice;
      }

      // హిందీకి 0.85 స్పీడ్ స్లోగా ఉండటం వల్ల క్రోమ్ ఆగిపోవచ్చు, అందుకే 0.9 లేదా 1.0 కి మార్చడమైనది
      utterance.rate = isHindi ? 0.95 : 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;

      utterance.onstart = () => console.log('🔊 TTS Started:', cleanText);
      const finish = () => {
        speakingRef.current = false;
        utteranceRef.current = [];
        speakRef.current?.();
      };
      utterance.onend = finish;
      utterance.onerror = (event) => {
        console.warn('🔊 TTS Error:', event.error);
        finish();
      };
      queueRef.current.push(utterance);
      speakRef.current?.();
    },
    [speakEnabled]
  );

  speakRef.current = () => {
    if (speakingRef.current || !queueRef.current.length) return;
    const next = queueRef.current.shift();
    speakingRef.current = true;
    utteranceRef.current = [next];
    window.speechSynthesis.speak(next);
  };

  return {
    speakEnabled,
    setSpeakEnabled,
    speak,
  };
}
