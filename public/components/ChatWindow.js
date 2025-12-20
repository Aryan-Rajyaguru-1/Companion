// ChatWindow Component
class ChatWindow {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.messages = [];
        this.conversationId = this.generateConversationId();
        this.init();
    }

    init() {
        this.render();
        this.bindEvents();
    }

    generateConversationId() {
        return 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    render() {
        this.container.innerHTML = `
            <div class="chat-window">
                <div class="chat-header">
                    <h2>Companion AI Chat</h2>
                    <div class="chat-controls">
                        <button id="new-chat-btn">New Chat</button>
                        <button id="clear-chat-btn">Clear</button>
                        <button id="export-chat-btn">Export</button>
                    </div>
                </div>
                <div class="messages-container" id="messages-container">
                    <div class="welcome-message">
                        <div class="message system">
                            <div class="message-header">
                                <span class="message-role">🤖 System</span>
                            </div>
                            <div class="message-content">
                                Welcome to Companion AI! I'm here to help you with various tasks.
                            </div>
                        </div>
                    </div>
                </div>
                <div class="input-container">
                    <div class="input-wrapper">
                        <textarea id="message-input" placeholder="Type your message..." rows="1"></textarea>
                        <button id="send-btn" disabled>Send</button>
                    </div>
                    <div class="typing-indicator" id="typing-indicator" style="display: none;">
                        <span>AI is thinking...</span>
                    </div>
                </div>
            </div>
        `;
    }

    bindEvents() {
        const input = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-btn');
        const newChatBtn = document.getElementById('new-chat-btn');
        const clearChatBtn = document.getElementById('clear-chat-btn');
        const exportChatBtn = document.getElementById('export-chat-btn');

        input.addEventListener('input', () => {
            sendBtn.disabled = !input.value.trim();
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        sendBtn.addEventListener('click', () => this.sendMessage());
        newChatBtn.addEventListener('click', () => this.newChat());
        clearChatBtn.addEventListener('click', () => this.clearChat());
        exportChatBtn.addEventListener('click', () => this.exportChat());
    }

    async sendMessage() {
        const input = document.getElementById('message-input');
        const message = input.value.trim();
        if (!message) return;

        // Add user message
        this.addMessage({
            id: this.generateMessageId(),
            role: 'user',
            type: 'user',
            content: message,
            timestamp: new Date().toISOString()
        });

        input.value = '';
        document.getElementById('send-btn').disabled = true;

        // Show typing indicator
        this.showTypingIndicator();

        try {
            // Use streaming
            const aiMessageId = this.generateMessageId();
            const aiMessage = {
                id: aiMessageId,
                role: 'assistant',
                type: 'assistant',
                agent: 'brain_agent',
                content: '',
                timestamp: new Date().toISOString()
            };
            this.addMessage(aiMessage);

            await chatApi.sendMessageStreaming(
                message,
                this.conversationId,
                (chunk) => {
                    // Update the AI message with streaming content
                    this.updateMessage(aiMessageId, chunk);
                },
                () => {
                    // Streaming complete
                    this.hideTypingIndicator();
                    document.getElementById('send-btn').disabled = false;
                },
                (error) => {
                    // Error occurred
                    this.hideTypingIndicator();
                    document.getElementById('send-btn').disabled = false;
                    this.addMessage({
                        id: this.generateMessageId(),
                        role: 'system',
                        type: 'error',
                        content: `Error: ${error.message}`,
                        timestamp: new Date().toISOString()
                    });
                }
            );
        } catch (error) {
            this.hideTypingIndicator();
            document.getElementById('send-btn').disabled = false;
            this.addMessage({
                id: this.generateMessageId(),
                role: 'system',
                type: 'error',
                content: `Error: ${error.message}`,
                timestamp: new Date().toISOString()
            });
        }
    }

    addMessage(message) {
        this.messages.push(message);
        this.renderMessage(message);
        this.scrollToBottom();
    }

    updateMessage(messageId, updatedMessage) {
        // Find the message in the array
        const messageIndex = this.messages.findIndex(msg => msg.id === messageId);
        if (messageIndex !== -1) {
            // Update the message
            this.messages[messageIndex] = { ...this.messages[messageIndex], ...updatedMessage };
            
            // Update the DOM
            const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
            if (messageEl) {
                const contentEl = messageEl.querySelector('.message-content');
                if (contentEl) {
                    contentEl.innerHTML = this.formatContent(updatedMessage.content || '');
                }
            }
        }
    }

    renderMessage(message) {
        const container = document.getElementById('messages-container');
        const messageEl = document.createElement('div');
        messageEl.className = `message ${message.role}`;
        messageEl.setAttribute('data-message-id', message.id);

        const roleIcon = this.getRoleIcon(message);
        const agentBadge = message.agent ? `<span class="agent-badge">${message.agent}</span>` : '';

        messageEl.innerHTML = `
            <div class="message-header">
                <span class="message-role">${roleIcon} ${message.role}</span>
                ${agentBadge}
                <span class="message-time">${this.formatTime(message.timestamp)}</span>
            </div>
            <div class="message-content">${this.formatContent(message.content)}</div>
        `;

        container.appendChild(messageEl);
    }

    getRoleIcon(message) {
        switch (message.type) {
            case 'agent': return '🧠';
            case 'system': return '⚙️';
            case 'error': return '⚠️';
            case 'user': return '👤';
            default: return '🤖';
        }
    }

    formatContent(content) {
        // Basic markdown-like formatting
        return content
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
    }

    formatTime(timestamp) {
        return new Date(timestamp).toLocaleTimeString();
    }

    generateMessageId() {
        return 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    showTypingIndicator() {
        document.getElementById('typing-indicator').style.display = 'block';
    }

    hideTypingIndicator() {
        document.getElementById('typing-indicator').style.display = 'none';
    }

    scrollToBottom() {
        const container = document.getElementById('messages-container');
        container.scrollTop = container.scrollHeight;
    }

    newChat() {
        this.conversationId = this.generateConversationId();
        this.clearChat();
    }

    clearChat() {
        this.messages = [];
        const container = document.getElementById('messages-container');
        container.innerHTML = '<div class="welcome-message"><div class="message system"><div class="message-header"><span class="message-role">🤖 System</span></div><div class="message-content">Chat cleared. Start a new conversation!</div></div></div>';
    }

    exportChat() {
        const data = {
            conversationId: this.conversationId,
            messages: this.messages,
            exportedAt: new Date().toISOString()
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat_${this.conversationId}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
}