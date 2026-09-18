import React, { useEffect, useRef } from 'react';

export function ConversationList({ messages, onSpeakText }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="glass-card conversation-section">
      <div className="conversation-header">
        <div className="conversation-title">
          <span>💬</span> LIVE CONVERSATION
        </div>
        <div style={{ fontSize: '0.8rem', color: '#9CA3AF' }}>
          {messages.length} {messages.length === 1 ? 'Message' : 'Messages'}
        </div>
      </div>

      <div className="conversation-list" ref={scrollRef}>
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#6B7280', padding: '3rem 1rem', fontStyle: 'italic' }}>
            No conversation messages yet. Press <strong>Start Conversation</strong> and speak naturally.
          </div>
        ) : (
          messages.map((msg) => {
            const isA = msg.speaker === 'person_a';
            const flag = isA ? '🇮🇳' : '🇬🇧';

            return (
              <div key={msg.id} className={`msg-card ${msg.speaker}`}>
                <div className="msg-header">
                  <div className="msg-speaker">
                    <span>{flag}</span>
                    <span>{msg.speaker_name}</span>
                    <span style={{ fontSize: '0.75rem', color: '#9CA3AF', fontWeight: '400' }}>
                      ({msg.source_language})
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span>{msg.timestamp}</span>
                    {onSpeakText && (
                      <button
                        className="tts-btn"
                        title="Speak translation aloud"
                        onClick={() => onSpeakText(msg.translation, msg.target_language === 'Hindi' ? 'hi' : 'en', true)}
                      >
                        🔊 Listen
                      </button>
                    )}
                  </div>
                </div>

                <div className="msg-content">
                  <div className="msg-original">
                    "{msg.original_text}"
                  </div>

                  <div className="msg-translation-box">
                    <div className="msg-translation-label">
                      {msg.target_language} Translation:
                    </div>
                    <div className="msg-translation-text">
                      "{msg.translation}"
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
