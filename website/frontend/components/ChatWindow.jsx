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
  const [state, setState] = useState(chatStore.state);
  const messagesEndRef = useRef(null);

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
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input, type: 'user' };
    chatStore.addMessage(userMessage);
    setInput('');

    chatStore.setTyping(true);
    try {
      const response = await chatApi.sendMessage(input);
      const assistantMessage = {
        role: 'assistant',
        content: response.response,
        type: 'assistant',
        agent: 'brain_agent', // Placeholder
        processingTime: response.processing_time,
      };
      chatStore.addMessage(assistantMessage);
    } catch (error) {
      chatStore.setError(error.message);
    } finally {
      chatStore.setTyping(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-window">
      <div className="chat-header">
        <h2>Companion Brain</h2>
        <AgentBadge agent="brain_agent" />
      </div>

      <div className="messages-container">
        {state.messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {state.isTyping && (
          <div className="typing-indicator">
            <span>AI is thinking...</span>
          </div>
        )}
        {state.error && (
          <div className="error-message">
            <span>⚠️ {state.error}</span>
            <button onClick={() => chatStore.clearError()}>Dismiss</button>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask me anything..."
          rows={1}
        />
        <button onClick={handleSend} disabled={!input.trim()}>
          Send
        </button>
      </div>

      <PermissionModal />
    </div>
  );
};

export default ChatWindow;