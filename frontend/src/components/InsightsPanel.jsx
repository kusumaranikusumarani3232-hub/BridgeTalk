import React from 'react';

export function InsightsPanel({ insights }) {
  // Filter duplicate insight items by label+value
  const uniqueInsights = insights.filter((item, index, self) =>
    index === self.findIndex((t) => t.label === item.label && t.value === item.value)
  );

  return (
    <div className="glass-card insights-panel">
      <div className="insights-title">
        <span>📊</span> Conversation Insights
      </div>

      {uniqueInsights.length === 0 ? (
        <div className="empty-insights">
          Structured facts (dates, times, locations, amounts) will appear here as you speak.
        </div>
      ) : (
        <div className="insights-list">
          {uniqueInsights.map((item, idx) => (
            <div key={idx} className="insight-item">
              <span className="insight-icon">{item.icon || '📌'}</span>
              <div className="insight-details">
                <span className="insight-label">{item.label}</span>
                <span className="insight-value">{item.value}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
