import React from 'react';

export function Header() {
  return (
    <header className="header-container glass-card">
      <div className="brand-section">
        <div className="brand-icon">🌐</div>
        <div>
          <h1 className="brand-title">BridgeTalk</h1>
          <p className="brand-tagline">Real-time conversations without language barriers</p>
        </div>
      </div>
      <div className="assemblyai-badge">
        <span>⚡</span> Powered by AssemblyAI Realtime Speech-to-Text
      </div>
    </header>
  );
}
