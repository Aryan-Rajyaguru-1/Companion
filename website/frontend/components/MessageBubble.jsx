// components/MessageBubble.jsx
// Individual message display component

import React from 'react';

const MessageBubble = ({ message, isStreaming = false }) => {
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
      const agentName = message.agent.replace('_', ' ').toUpperCase();
      return (
        <span className="agent-badge" title={`Response from ${agentName} agent`}>
          {message.agent}
        </span>
      );
    }
    return null;
  };

  const formatContent = (content) => {
    if (!content) return '';

    // Basic markdown-like formatting
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  };

  return (
    <div className={`message-bubble ${message.role} ${isStreaming ? 'streaming' : ''}`}>
      <div className="message-header">
        <span className="message-icon">{getMessageIcon()}</span>
        {getAgentBadge()}
        <span className="timestamp">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
        {isStreaming && <span className="streaming-indicator">⏳</span>}
      </div>
      <div
        className="message-content"
        dangerouslySetInnerHTML={{ __html: formatContent(message.content) }}
      />
      {message.processingTime && (
        <div className="processing-time">
          Processed in {(message.processingTime * 1000).toFixed(0)}ms
        </div>
      )}
      {isStreaming && (
        <div className="streaming-cursor">|</div>
      )}
    </div>
  );
};

export default MessageBubble;