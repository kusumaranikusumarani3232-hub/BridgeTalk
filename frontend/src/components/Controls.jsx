import React from 'react';

export function Controls({
  isRecording,
  onStart,
  onStop,
  onClear,
  onRunDemo,
  speakEnabled,
  onToggleSpeak,
  isDemoActive,
}) {
  return (
    <div className="glass-card controls-bar">
      <div className="action-buttons">
        {!isRecording ? (
          <button className="btn btn-start" onClick={onStart}>
            <span>🎙️</span> Start Conversation
          </button>
        ) : (
          <button className="btn btn-stop" onClick={onStop}>
            <span>⏹️</span> Stop Conversation
          </button>
        )}

        <button className="btn btn-secondary" onClick={onClear}>
          🗑️ Clear
        </button>

        <button className="btn btn-secondary" onClick={onRunDemo}>
          ▶ Demo Mode (No Credits)
        </button>
      </div>

      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={speakEnabled}
          onChange={(e) => onToggleSpeak(e.target.checked)}
        />
        <span>🔊 Speak translations</span>
      </label>
    </div>
  );
}
