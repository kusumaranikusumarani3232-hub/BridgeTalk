import React from 'react';

export function LiveTranscriptArea({ partialTranscript, isRecording, activeSpeaker }) {
  if (!isRecording && !partialTranscript) {
    return null;
  }

  const speakerLabel = activeSpeaker === 'person_a' ? 'Person A (Hindi)' : 'Person B (English)';

  return (
    <div className="glass-card live-transcript-card">
      <div className="live-indicator">
        <span className="dot online pulsing" style={{ backgroundColor: '#F43F5E' }}></span>
        🎙️ Listening to {speakerLabel}...
      </div>
      <div className="live-text">
        {partialTranscript?.text ? `"${partialTranscript.text}"` : 'Listening for speech...'}
      </div>
    </div>
  );
}
