import React, { useState, useEffect } from 'react';

import { Header } from './components/Header';
import { ConnectionStatus } from './components/ConnectionStatus';
import { SpeakerSelector } from './components/SpeakerSelector';
import { LiveTranscriptArea } from './components/LiveTranscriptArea';
import { ConversationList } from './components/ConversationList';
import { InsightsPanel } from './components/InsightsPanel';
import { Controls } from './components/Controls';
import { DemoModeBanner } from './components/DemoModeBanner';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioRecorder } from './hooks/useAudioRecorder';
import { useSpeechSynthesis } from './hooks/useSpeechSynthesis';

export default function App() {
  const [isDemoActive, setIsDemoActive] = useState(false);

  // Custom Hooks
  const {
    isConnected,
    assemblyaiReady,
    statusMessage,
    partialTranscript,
    messages,
    insights,
    activeSpeaker,
    setActiveSpeaker,
    sendAction,
    sendAudioChunk,
    clearConversation,
  } = useWebSocket();

  const {
    isRecording,
    permissionError,
    startRecording,
    stopRecording,
  } = useAudioRecorder(sendAudioChunk);

  const {
    speakEnabled,
    setSpeakEnabled,
    speak,
  } = useSpeechSynthesis();

  const lastSpokenIdRef = React.useRef(null);

  // Speak each new final message only once when speech is enabled
  useEffect(() => {
    if (!speakEnabled || messages.length === 0) {
      return;
    }

    const latestMsg = messages[messages.length - 1];

    if (
      !latestMsg?.id ||
      lastSpokenIdRef.current === latestMsg.id
    ) {
      return;
    }

    lastSpokenIdRef.current = latestMsg.id;

    const targetLanguage = String(
      latestMsg.target_language || ''
    ).toLowerCase();

    const targetLangCode =
      targetLanguage.includes('hindi') ||
        targetLanguage === 'hi'
        ? 'hi'
        : 'en';

    console.log('🔊 Speaking new message:', {
      id: latestMsg.id,
      text: latestMsg.translation,
      target_language: latestMsg.target_language,
      targetLangCode,
    });

    speak(latestMsg.translation, targetLangCode);
  }, [messages, speakEnabled, speak]);

  const handleStartConversation = async () => {
    setIsDemoActive(false);
    await startRecording();
    sendAction('start');
  };

  const handleStopConversation = () => {
    stopRecording();
    sendAction('stop');
  };

  const handleRunDemo = () => {
    stopRecording();
    setIsDemoActive(true);
    sendAction('start_demo');
  };

  return (
    <div className="app-container">
      <Header />

      <ConnectionStatus
        isConnected={isConnected}
        assemblyaiReady={assemblyaiReady}
        statusMessage={permissionError || statusMessage}
        isRecording={isRecording}
      />

      <DemoModeBanner
        isDemoActive={isDemoActive}
        onDismiss={() => setIsDemoActive(false)}
      />

      <SpeakerSelector
        activeSpeaker={activeSpeaker}
        onSelectSpeaker={setActiveSpeaker}
        isRecording={isRecording}
      />

      <LiveTranscriptArea
        partialTranscript={partialTranscript}
        isRecording={isRecording}
        activeSpeaker={activeSpeaker}
      />

      <div className="main-grid">
        <ConversationList
          messages={messages}
          onSpeakText={speak}
        />

        <InsightsPanel insights={insights} />
      </div>

      <Controls
        isRecording={isRecording}
        onStart={handleStartConversation}
        onStop={handleStopConversation}
        onClear={clearConversation}
        onRunDemo={handleRunDemo}
        speakEnabled={speakEnabled}
        onToggleSpeak={setSpeakEnabled}
        isDemoActive={isDemoActive}
      />

      <footer className="footer-credits">
        BridgeTalk © 2026 — Built for lablab.ai × AssemblyAI Hackathon
      </footer>
    </div>
  );
}