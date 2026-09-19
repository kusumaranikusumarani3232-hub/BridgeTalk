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

      // ఇంజిన్ రీసెట్ మరియు పాత స్పీచ్ క్యాన్సిల్
      speechIdRef.current += 1;
      const currentSpeechId = speechIdRef.current;
      speech.cancel();

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

      // హిందీ టెక్స్ట్ సైజ్ బట్టి ముక్కలుగా విడదీయడం (Safe Chunking)
      const chunks = [];
      if (isHindi) {
        // హిందీకి పదాల కంటే క్యారెక్టర్ల (Characters) బట్టి ముక్కలు చేయడం సురక్షితం (ప్రతి 60 అక్షరాలకు ఒక ముక్క)
        const size = 60;
        for (let i = 0; i < cleanText.length; i += size) {
          chunks.push(cleanText.substring(i, i + size));
        }
      } else {
        chunks.push(cleanText);
      }

      utteranceRef.current = [];

      const speakChunk = (index) => {
        if (currentSpeechId !== speechIdRef.current) return;
        if (index >= chunks.length) {
          utteranceRef.current = [];
          return;
        }

        const utterance = new SpeechSynthesisUtterance(chunks[index]);

        // వాయిస్ సెట్టింగ్స్
        utterance.lang = matchingVoice ? matchingVoice.lang : (isHindi ? 'hi-IN' : 'en-US');
        if (matchingVoice) {
          utterance.voice = matchingVoice;
        }

        // హిందీకి 0.85 స్పీడ్ స్లోగా ఉండటం వల్ల క్రోమ్ ఆగిపోవచ్చు, అందుకే 0.9 లేదా 1.0 కి మార్చడమైనది
        utterance.rate = isHindi ? 0.95 : 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        utterance.onstart = () => {
          console.log('🔊 TTS Started:', chunks[index]);
        };

        utterance.onend = () => {
          if (currentSpeechId !== speechIdRef.current) return;
          setTimeout(() => {
            speakChunk(index + 1);
          }, 50); // చంక్స్ మధ్య గ్యాప్ తగ్గించబడింది
        };

        utterance.onerror = (event) => {
          console.warn('🔊 TTS Error:', event.error);
          // ఒకవేళ క్రోమ్ అడ్డుకుంటే (interrupted) మళ్లీ ప్రయత్నించడానికి
          if (event.error === 'interrupted' && currentSpeechId === speechIdRef.current) {
            // సిస్టమ్ ఆగిపోకుండా నెక్స్ట్ ముక్కకు వెళ్తుంది
            speakChunk(index + 1);
          }
        };

        utteranceRef.current.push(utterance);
        speech.speak(utterance);
      };

      // బ్రౌజర్ క్యూ సెటిల్ అవ్వడానికి సమయం (Timeout 300ms కి పెంచబడింది)
      setTimeout(() => {
        if (currentSpeechId === speechIdRef.current) {
          speakChunk(0);
        }
      }, 300);
    },
    [speakEnabled]
  );

  return {
    speakEnabled,
    setSpeakEnabled,
    speak,
  };
}
