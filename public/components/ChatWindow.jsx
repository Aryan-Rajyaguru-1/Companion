// components/ChatWindow.jsx
// Main chat interface component

import React, { useState, useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';
import AgentBadge from './AgentBadge';
import PermissionModal from './PermissionModal';
import chatApi from '../services/chatApi';
import chatStore from '../state/chatStore';

const ChatWindow = () => {
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessageId, setCurrentStreamingMessageId] = useState(null);
  const [state, setState] = useState(chatStore.state);
  const messagesEndRef = useRef(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    const unsubscribe = chatStore.subscribe(setState);
    return unsubscribe;
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [state.messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

    const userMessage = {
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      role: 'user',
      content: input.trim(),
      type: 'user',
      timestamp: new Date().toISOString()
    };

    chatStore.addMessage(userMessage);
    const messageToSend = input.trim();
    setInput('');

    // Start streaming response
    await startStreamingResponse(messageToSend, state.currentConversationId);
  };

  const startStreamingResponse = async (message, conversationId) => {
    setIsStreaming(true);
    chatStore.setTyping(true);

    try {
      // Create streaming message placeholder
      const streamingMessageId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      setCurrentStreamingMessageId(streamingMessageId);

      const streamingMessage = {
        id: streamingMessageId,
        role: 'assistant',
        content: '',
        type: 'assistant',
        timestamp: new Date().toISOString(),
        isStreaming: true
      };

      chatStore.addMessage(streamingMessage);

      // Start Server-Sent Events
      const eventSource = new EventSource(
        `${chatApi.baseUrl}/v1/chat/stream`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': chatApi.apiKey
          },
          body: JSON.stringify({
            message: message,
            conversation_id: conversationId,
            stream: true
          }),
          method: 'POST'
        }
      );

      eventSourceRef.current = eventSource;

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'chunk') {
            // Update streaming message content
            chatStore.updateMessage(streamingMessageId, {
              content: data.content,
              agent: data.metadata?.agent
            });
          } else if (data.type === 'done') {
            // Finalize streaming message
            chatStore.updateMessage(streamingMessageId, {
              content: data.content,
              agent: data.metadata?.agent,
              isStreaming: false,
              processingTime: data.metadata?.processing_time
            });
            finishStreaming();
          }
        } catch (error) {
          console.error('Error parsing streaming data:', error);
          finishStreaming();
        }
      };

      eventSource.onerror = (error) => {
        console.error('Streaming error:', error);
        chatStore.setError('Connection lost during streaming. Please try again.');
        finishStreaming();
      };

    } catch (error) {
      console.error('Error starting stream:', error);
      chatStore.setError('Failed to start streaming response. Please try again.');
      finishStreaming();
    }
  };

  const finishStreaming = () => {
    setIsStreaming(false);
    setCurrentStreamingMessageId(null);
    chatStore.setTyping(false);

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleStopStreaming = () => {
    finishStreaming();
  };

  return (
    <div className="chat-window">
      <div className="chat-header">
        <h2>Companion Brain</h2>
        <div className="header-controls">
          <AgentBadge agent="brain_agent" />
          {isStreaming && (
            <button
              className="stop-streaming-btn"
              onClick={handleStopStreaming}
              title="Stop streaming response"
            >
              ⏹️ Stop
            </button>
          )}
        </div>
      </div>

      <div className="messages-container">
        {state.messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            isStreaming={message.id === currentStreamingMessageId}
          />
        ))}
        {state.isTyping && !isStreaming && (
          <div className="typing-indicator">
            <span>AI is thinking...</span>
          </div>
        )}
        {state.error && (
          <div className="error-banner">
            <div className="error-content">
              <span className="error-icon">⚠️</span>
              <span className="error-message">{state.error}</span>
              <button
                className="error-dismiss"
                onClick={() => chatStore.clearError()}
                title="Dismiss error"
              >
                ✕
              </button>
            </div>
            <div className="error-actions">
              <button
                className="error-retry"
                onClick={() => handleSend()}
                disabled={isStreaming}
              >
                Retry
              </button>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input">
        <div className="input-container">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask me anything..."
            rows={1}
            disabled={isStreaming}
            maxLength={10000}
          />
          <div className="input-controls">
            <span className="char-count">
              {input.length}/10000
            </span>
            <button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className={isStreaming ? 'sending' : ''}
            >
              {isStreaming ? '⏳' : 'Send'}
            </button>
          </div>
        </div>
      </div>

      <PermissionModal />
    </div>
  );
};

export default ChatWindow;