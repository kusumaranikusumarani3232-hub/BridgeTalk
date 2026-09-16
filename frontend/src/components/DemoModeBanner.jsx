import React from 'react';

export function DemoModeBanner({ isDemoActive, onDismiss }) {
  if (!isDemoActive) return null;

  return (
    <div className="demo-banner">
      <div>
        ⚡ <strong>Demo Mode — Prerecorded Example</strong> (Zero AssemblyAI credit usage)
      </div>
      <button
        onClick={onDismiss}
        style={{
          background: 'transparent',
          border: 'none',
          color: '#F59E0B',
          cursor: 'pointer',
          fontWeight: 'bold',
        }}
      >
        ✕ Close
      </button>
    </div>
  );
}
