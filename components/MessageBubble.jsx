// components/MessageBubble.jsx
// Individual message display component

import React from 'react';

const MessageBubble = ({ message }) => {
  const getMessageIcon = () => {
    switch (message.type) {
      case 'user': return '👤';
      case 'assistant': return '🤖';
      case 'agent': return '⚙️';
      case 'system': return '🔔';
      case 'error': return '⚠️';
      default: return '💬';
    }
  };

  const getAgentBadge = () => {
    if (message.agent) {
      return <span className="agent-badge">{message.agent}</span>;
    }
    return null;
  };

  return (
    <div className={`message-bubble ${message.role}`}>
      <div className="message-header">
        <span className="message-icon">{getMessageIcon()}</span>
        {getAgentBadge()}
        <span className="timestamp">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
      <div className="message-content">
        {message.content}
      </div>
      {message.processingTime && (
        <div className="processing-time">
          Processed in {message.processingTime.toFixed(2)}s
        </div>
      )}
    </div>
  );
};

export default MessageBubble;