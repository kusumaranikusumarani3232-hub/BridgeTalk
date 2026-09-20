import { useState, useRef, useCallback, useEffect } from 'react';

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [assemblyaiReady, setAssemblyaiReady] = useState(false);
  const [statusMessage, setStatusMessage] = useState('Connecting...');
  const [partialTranscript, setPartialTranscript] = useState(null);
  const [messages, setMessages] = useState([]);
  const [insights, setInsights] = useState([]);
  const [activeSpeaker, setActiveSpeakerState] = useState('person_a');

  const wsRef = useRef(null);
  const isConnectingRef = useRef(false);

  const connect = useCallback(() => {
    // Prevent duplicate simultaneous connections
    if (isConnectingRef.current) return;
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    isConnectingRef.current = true;
    const wsUrl = 'wss://bridgetalk-olvd.onrender.com/ws/transcribe';
    console.log('Connecting WebSocket to:', wsUrl);

    let ws;
    try {
      ws = new WebSocket(wsUrl);
    } catch (e) {
      console.error('WebSocket constructor failed:', e);
      isConnectingRef.current = false;
      setStatusMessage('Unable to connect to backend server.');
      return;
    }

    wsRef.current = ws;

    ws.onopen = () => {
      isConnectingRef.current = false;
      setIsConnected(true);
      setStatusMessage('Connected to BridgeTalk backend.');
      console.log('WebSocket connected.');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'status') {
          setIsConnected(data.connected);
          setAssemblyaiReady(data.assemblyai_ready);
          if (data.speaker) setActiveSpeakerState(data.speaker);
          setStatusMessage(data.message);
        } else if (data.type === 'partial') {
          setPartialTranscript(data);
          if (data.speaker) setActiveSpeakerState(data.speaker);
        } else if (data.type === 'final') {
          setPartialTranscript(null);
          if (data.speaker) setActiveSpeakerState(data.speaker);
          const finalPayload = {
            id: data.id || Date.now(),
            speaker: data.speaker,
            speaker_name: data.speaker_name,
            source_language: data.source_language,
            target_language: data.target_language,
            original_text: data.original_text,
            translation: data.translation || data.original_text,
            insights: data.insights || [],
          };
          setMessages((prev) => [...prev, finalPayload]);
          if (data.insights && data.insights.length > 0) {
            setInsights((prev) => {
              // Merge insights without duplicates
              const newInsights = data.insights.filter(
                (ni) => !prev.some((pi) => pi.label === ni.label && pi.value === ni.value)
              );
              return [...prev, ...newInsights];
            });
          }
        }
      } catch (err) {
        console.error('Error parsing WebSocket message:', err, event.data);
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      isConnectingRef.current = false;
      setStatusMessage('Connection error. Is the backend server running on port 8000?');
      setIsConnected(false);
    };

    ws.onclose = (evt) => {
      isConnectingRef.current = false;
      // Only update state if this is still the current ws reference
      if (wsRef.current === ws) {
        wsRef.current = null;
        setIsConnected(false);
        setAssemblyaiReady(false);
        setStatusMessage(`Disconnected (code ${evt.code}). Reconnecting in 3s...`);
        console.log('WebSocket closed, code:', evt.code);
        // Auto-reconnect after 3s if not a normal closure
        if (evt.code !== 1000) {
          setTimeout(() => {
            if (!wsRef.current) connect();
          }, 3000);
        }
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      const ws = wsRef.current;
      wsRef.current = null;
      ws.onclose = null; // Prevent auto-reconnect
      ws.close(1000, 'User disconnected');
    }
    isConnectingRef.current = false;
    setIsConnected(false);
    setAssemblyaiReady(false);
  }, []);

  const sendAction = useCallback((action, payload = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...payload }));
    } else {
      console.warn('WebSocket not open, cannot send action:', action);
    }
  }, []);

  const sendAudioChunk = useCallback((arrayBuffer) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(arrayBuffer);
    }
  }, []);

  const clearConversation = useCallback(() => {
    setMessages([]);
    setInsights([]);
    setPartialTranscript(null);
  }, []);

  const setActiveSpeaker = useCallback((speaker) => {
    setActiveSpeakerState(speaker);
    sendAction('set_speaker', { speaker });
  }, [sendAction]);

  useEffect(() => {
    connect();
    return () => {
      // On unmount, disconnect cleanly without auto-reconnect
      if (wsRef.current) {
        const ws = wsRef.current;
        wsRef.current = null;
        ws.onclose = null;
        ws.close(1000, 'Component unmounted');
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    isConnected,
    assemblyaiReady,
    statusMessage,
    partialTranscript,
    messages,
    insights,
    activeSpeaker,
    setActiveSpeaker,
    connect,
    disconnect,
    sendAction,
    sendAudioChunk,
    clearConversation,
    setMessages,
  };
}
