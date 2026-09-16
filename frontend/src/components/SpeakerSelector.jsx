import React from 'react';

export function SpeakerSelector({ activeSpeaker, onSelectSpeaker, isRecording }) {
  const isA = activeSpeaker === 'person_a';
  const isB = activeSpeaker === 'person_b';

  return (
    <div className="speakers-grid">
      {/* Person A Card */}
      <div 
        className={`glass-card speaker-card ${isA ? 'active-a' : ''}`}
        onClick={() => onSelectSpeaker('person_a')}
      >
        <div className="speaker-header">
          <div className="speaker-info">
            <span className="speaker-flag">🇮🇳</span>
            <div>
              <div className="speaker-name">Person A</div>
              <div className="speaker-lang">Hindi (हिन्दी)</div>
            </div>
          </div>
          <div className={`mic-badge ${isA && isRecording ? 'active' : 'inactive'}`}>
            {isA && isRecording ? '🎙️ Active Mic' : 'Standby'}
          </div>
        </div>

        <button 
          className="speak-btn speak-btn-a"
          onClick={(e) => {
            e.stopPropagation();
            onSelectSpeaker('person_a');
          }}
        >
          {isA ? '✓ Speaking as Person A' : 'Speak as Person A (Hindi)'}
        </button>
      </div>

      {/* Person B Card */}
      <div 
        className={`glass-card speaker-card ${isB ? 'active-b' : ''}`}
        onClick={() => onSelectSpeaker('person_b')}
      >
        <div className="speaker-header">
          <div className="speaker-info">
            <span className="speaker-flag">🇬🇧</span>
            <div>
              <div className="speaker-name">Person B</div>
              <div className="speaker-lang">English</div>
            </div>
          </div>
          <div className={`mic-badge ${isB && isRecording ? 'active' : 'inactive'}`}>
            {isB && isRecording ? '🎙️ Active Mic' : 'Standby'}
          </div>
        </div>

        <button 
          className="speak-btn speak-btn-b"
          onClick={(e) => {
            e.stopPropagation();
            onSelectSpeaker('person_b');
          }}
        >
          {isB ? '✓ Speaking as Person B' : 'Speak as Person B (English)'}
        </button>
      </div>
    </div>
  );
}
