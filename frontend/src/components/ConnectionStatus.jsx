import React from 'react';

export function ConnectionStatus({ isConnected, assemblyaiReady, statusMessage, isRecording }) {
  return (
    <div className="status-bar glass-card">
      <div className="status-indicator">
        <span className={`dot ${isConnected ? 'online' : 'offline'}`}></span>
        <span>Backend: <strong>{isConnected ? 'Connected' : 'Disconnected'}</strong></span>
      </div>

      <div className="status-indicator">
        <span className={`dot ${assemblyaiReady ? 'online pulsing' : 'offline'}`}></span>
        <span>AssemblyAI: <strong>{assemblyaiReady ? 'Ready' : 'Standby / Stopped'}</strong></span>
      </div>

      {isRecording && (
        <div className="status-indicator" style={{ color: '#F43F5E' }}>
          <span className="dot online pulsing" style={{ backgroundColor: '#F43F5E' }}></span>
          <span>Mic Active (Streaming Audio)</span>
        </div>
      )}

      <div style={{ marginLeft: 'auto', color: '#9CA3AF', fontSize: '0.8rem' }}>
        {statusMessage}
      </div>
    </div>
  );
}
