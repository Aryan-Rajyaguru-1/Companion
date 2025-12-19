// Modern Chat Interface JavaScript

class ModernChatInterface {
    constructor() {
        this.currentChatId = null;
        this.chatHistory = [];
        this.isWelcomeState = true;
        this.apiBaseUrl = 'http://localhost:5000/api';
        
        this.initializeElements();
        this.bindEvents();
        this.loadChatHistory();
    }

    initializeElements() {
        console.log('Initializing elements...');
        
        // Main elements
        this.welcomeState = document.getElementById('welcomeState');
        this.chatMessages = document.getElementById('chatMessages');
        this.inputArea = document.getElementById('inputArea');
        
        console.log('Main elements:', { 
            welcomeState: !!this.welcomeState, 
            chatMessages: !!this.chatMessages, 
            inputArea: !!this.inputArea 
        });
        
        // Input elements
        this.chatInput = document.getElementById('chatInput');
        this.chatTextarea = document.getElementById('chatTextarea');
        this.sendBtn = document.getElementById('sendBtn');
        this.sendMessageBtn = document.getElementById('sendMessageBtn');
        this.charCount = document.getElementById('charCount');
        
        // Control elements
        this.newChatBtn = document.getElementById('newChatBtn');
        this.clearChatBtn = document.getElementById('clearChatBtn');
        this.toolsBtn = document.getElementById('toolsBtn');
        this.toolsDropdown = document.getElementById('toolsDropdown');
        this.voiceBtn = document.getElementById('voiceBtn');
        
        // Quick actions
        this.quickActions = document.querySelectorAll('.quick-action');
        this.toolItems = document.querySelectorAll('.tool-item');
        this.historyItems = document.querySelectorAll('.history-item');
        
        console.log('Input elements:', { 
            chatInput: !!this.chatInput, 
            sendBtn: !!this.sendBtn,
            newChatBtn: !!this.newChatBtn
        });
    }

    bindEvents() {
        // Send message events
        this.sendBtn?.addEventListener('click', () => this.handleSendMessage());
        this.sendMessageBtn?.addEventListener('click', () => this.handleSendMessage());
        
        // Input events
        this.chatInput?.addEventListener('keydown', (e) => this.handleKeyDown(e, 'search'));
        this.chatTextarea?.addEventListener('keydown', (e) => this.handleKeyDown(e, 'chat'));
        this.chatTextarea?.addEventListener('input', () => this.updateCharCount());
        
        // Control events
        this.newChatBtn?.addEventListener('click', () => this.startNewChat());
        this.clearChatBtn?.addEventListener('click', () => this.clearCurrentChat());
        this.toolsBtn?.addEventListener('click', () => this.toggleToolsDropdown());
        
        // Quick actions
        this.quickActions.forEach(action => {
            action.addEventListener('click', () => {
                const prompt = action.dataset.prompt;
                this.sendMessage(prompt);
            });
        });
        
        // Tool items
        this.toolItems.forEach(item => {
            item.addEventListener('click', () => {
                const tool = item.dataset.tool;
                this.selectTool(tool);
            });
        });
        
        // Click outside to close dropdowns
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.tools-dropdown') && !e.target.closest('.tools-btn')) {
                this.toolsDropdown?.classList.remove('show');
            }
        });
        
        // Auto-resize textarea
        if (this.chatTextarea) {
            this.chatTextarea.addEventListener('input', () => this.autoResizeTextarea());
        }
    }

    handleKeyDown(e, type) {
        if (e.key === 'Enter') {
            if (e.shiftKey) {
                // Allow new line
                return;
            } else {
                e.preventDefault();
                this.handleSendMessage();
            }
        }
    }

    handleSendMessage() {
        const message = this.isWelcomeState ? 
            this.chatInput?.value.trim() : 
            this.chatTextarea?.value.trim();
            
        if (!message) return;
        
        this.sendMessage(message);
        
        // Clear input
        if (this.isWelcomeState) {
            this.chatInput.value = '';
        } else {
            this.chatTextarea.value = '';
            this.updateCharCount();
            this.autoResizeTextarea();
        }
    }

    async sendMessage(message, tool = null) {
        // Switch to chat view if in welcome state
        if (this.isWelcomeState) {
            this.switchToChatView();
        }
        
        // Create new conversation if none exists
        if (!this.currentChatId) {
            await this.createNewConversation();
        }
        
        // Add user message to UI immediately
        this.addMessage('user', message);
        
        // Show typing indicator
        this.showTypingIndicator();
        
        try {
            // Send message to backend
            const response = await fetch(`${this.apiBaseUrl}/conversations/${this.currentChatId}/messages`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });
            
            if (!response.ok) {
                throw new Error('Failed to send message');
            }
            
            const data = await response.json();
            
            // Remove typing indicator
            this.removeTypingIndicator();
            
            // Add AI response with learned status
            this.addMessage('assistant', data.assistant_message.content, data.message_id, data.is_learned || false);
            
            // Update chat history sidebar
            this.loadChatHistory();
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.removeTypingIndicator();
            this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        }
    }

    addMessage(type, content, messageId = null, isLearned = false) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${type}-message`;
        messageElement.dataset.messageId = messageId || this.generateMessageId();
        
        const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        if (type === 'user') {
            messageElement.innerHTML = `
                <div class="message-bubble">
                    <div class="message-header">
                        <span class="message-avatar">👤</span>
                        <span class="message-sender">You</span>
                        <span class="message-time">${time}</span>
                    </div>
                    <div class="message-content">
                        ${this.formatMessage(content)}
                    </div>
                </div>
            `;
        } else {
            messageElement.innerHTML = `
                <div class="message-bubble">
                    <div class="message-header">
                        <span class="message-avatar">🤖</span>
                        <span class="message-sender">Companion</span>
                        <span class="message-time">${time}</span>
                    </div>
                    <div class="message-content">
                        ${this.formatMessage(content)}
                    </div>
                    <div class="message-footer">
                        <div class="message-status">
                            ${isLearned ? '<span class="status-icon status-learned">◉</span><span>Adaptive Response</span>' : ''}
                        </div>
                        <div class="message-actions-row">
                            <button class="msg-action-btn" data-action="copy" title="Copy response">
                                <span>📋</span>
                                <span class="btn-text">Copy</span>
                            </button>
                            <button class="msg-action-btn" data-action="regenerate" title="Regenerate response">
                                <span>🔄</span>
                                <span class="btn-text">Regenerate</span>
                            </button>
                            <div class="feedback-container">
                                <button class="feedback-btn" data-feedback="like" title="Good response">👍</button>
                                <button class="feedback-btn" data-feedback="dislike" title="Poor response">👎</button>
                                <button class="msg-action-btn comment-btn" data-action="comment" title="Add comment">
                                    <span>💬</span>
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="message-action-panel" id="actionPanel-${messageElement.dataset.messageId}">
                        <!-- Dynamic action panel content -->
                    </div>
                </div>
            `;
        }
        
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
        
        // Add event listeners for assistant messages
        if (type === 'assistant') {
            this.setupMessageEventListeners(messageElement, content);
        }
    }

    generateMessageId() {
        return 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    setupMessageEventListeners(messageElement, content) {
        const messageId = messageElement.dataset.messageId;
        
        // Message action listeners for the new button structure
        const actionBtns = messageElement.querySelectorAll('.msg-action-btn');
        actionBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const actionType = btn.getAttribute('data-action');
                this.handleMessageAction(actionType, content, messageElement);
            });
        });
        
        // Feedback listeners
        const feedbackBtns = messageElement.querySelectorAll('.feedback-btn');
        feedbackBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const feedbackType = btn.getAttribute('data-feedback');
                this.handleFeedback(messageId, feedbackType, content, btn, messageElement);
            });
        });
    }

    formatMessage(content) {
        // Basic markdown-like formatting
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    async handleFeedback(messageId, feedbackType, content, btnElement, messageElement) {
        try {
            // Visual feedback immediately
            const allFeedbackBtns = messageElement.querySelectorAll('.feedback-btn');
            allFeedbackBtns.forEach(btn => {
                btn.classList.remove('liked', 'disliked');
            });
            
            if (feedbackType === 'like') {
                btnElement.classList.add('liked');
                this.showFeedbackThankYou(messageElement, 'positive');
            } else if (feedbackType === 'dislike') {
                btnElement.classList.add('disliked');
                this.showFeedbackForm(messageElement, messageId, content);
            }
            
            // Send feedback to backend
            if (this.currentChatId) {
                const response = await fetch(`${this.apiBaseUrl}/feedback`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        conversation_id: this.currentChatId,
                        message_id: messageId,
                        feedback_type: feedbackType,
                        message_content: content
                    })
                });
                
                if (!response.ok) {
                    console.warn('Failed to save feedback to backend');
                }
            }
            
        } catch (error) {
            console.error('Error handling feedback:', error);
        }
    }

    showFeedbackThankYou(messageElement, type) {
        const actionPanel = messageElement.querySelector('.message-action-panel');
        actionPanel.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px; color: var(--success-color); font-size: 13px;">
                <span>✓</span>
                <span>Thanks for your feedback! This helps improve responses.</span>
            </div>
        `;
        actionPanel.classList.add('show');
        
        // Hide after 3 seconds
        setTimeout(() => {
            actionPanel.classList.remove('show');
        }, 3000);
    }

    showFeedbackForm(messageElement, messageId, content) {
        const actionPanel = messageElement.querySelector('.message-action-panel');
        actionPanel.innerHTML = `
            <div>
                <div style="margin-bottom: 8px; font-size: 13px; color: var(--text-secondary);">
                    Help us improve - what went wrong?
                </div>
                <textarea class="feedback-comment" 
                          placeholder="Optional: Describe what could be better..."
                          rows="2"></textarea>
                <div class="feedback-submit">
                    <button class="feedback-submit-btn secondary" onclick="this.closest('.message-action-panel').classList.remove('show')">
                        Cancel
                    </button>
                    <button class="feedback-submit-btn primary" onclick="window.chatInterface.submitFeedbackComment(this, '${messageId}', '${content}')">
                        Submit
                    </button>
                </div>
            </div>
        `;
        actionPanel.classList.add('show');
    }

    async submitFeedbackComment(button, messageId, content) {
        const actionPanel = button.closest('.message-action-panel');
        const textarea = actionPanel.querySelector('.feedback-comment');
        const comment = textarea.value.trim();
        
        try {
            if (this.currentChatId && comment) {
                const response = await fetch(`${this.apiBaseUrl}/feedback`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        conversation_id: this.currentChatId,
                        message_id: messageId,
                        feedback_type: 'dislike',
                        message_content: content,
                        comment: comment
                    })
                });
                
                if (response.ok) {
                    actionPanel.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px; color: var(--success-color); font-size: 13px;">
                            <span>✓</span>
                            <span>Feedback submitted! We'll use this to improve future responses.</span>
                        </div>
                    `;
                } else {
                    throw new Error('Failed to submit feedback');
                }
            } else {
                actionPanel.classList.remove('show');
            }
            
            // Hide after 3 seconds
            setTimeout(() => {
                actionPanel.classList.remove('show');
            }, 3000);
            
        } catch (error) {
            console.error('Error submitting feedback comment:', error);
            actionPanel.innerHTML = `
                <div style="color: var(--danger-color); font-size: 13px;">
                    <span>×</span> Failed to submit feedback. Please try again.
                </div>
            `;
        }
    }

    handleMessageAction(action, content, messageElement) {
        const messageId = messageElement.dataset.messageId;
        const actionPanel = messageElement.querySelector('.message-action-panel');
        
        switch (action) {
            case 'copy':
                this.copyToClipboard(content);
                this.showTemporaryStatus(messageElement, 'Copied to clipboard!', 'success');
                break;
                
            case 'regenerate':
                this.regenerateResponse(messageElement);
                break;
                
            case 'comment':
                this.showCommentForm(messageElement, messageId, content);
                break;
                
            default:
                console.log(`Action ${action} not implemented yet`);
        }
    }

    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
        } catch (err) {
            console.error('Failed to copy text:', err);
        }
    }

    showTemporaryStatus(messageElement, message, type = 'info') {
        const actionPanel = messageElement.querySelector('.message-action-panel');
        const color = type === 'success' ? 'var(--success-color)' : 
                     type === 'error' ? 'var(--danger-color)' : 'var(--accent-color)';
        
        actionPanel.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px; color: ${color}; font-size: 13px;">
                <span>${type === 'success' ? '✓' : type === 'error' ? '×' : 'i'}</span>
                <span>${message}</span>
            </div>
        `;
        actionPanel.classList.add('show');
        
        setTimeout(() => {
            actionPanel.classList.remove('show');
        }, 2000);
    }

    switchToChatView() {
        this.isWelcomeState = false;
        this.welcomeState.style.display = 'none';
        this.chatMessages.style.display = 'block';
        this.inputArea.style.display = 'block';
        
        // Update chat title
        const chatTitle = document.querySelector('.chat-title');
        if (chatTitle) {
            chatTitle.textContent = 'New Conversation';
        }
    }

    async startNewChat() {
        this.currentChatId = null;
        this.isWelcomeState = true;
        this.welcomeState.style.display = 'flex';
        this.chatMessages.style.display = 'none';
        this.inputArea.style.display = 'none';
        
        // Clear messages
        this.chatMessages.innerHTML = '';
        
        // Update chat title
        const chatTitle = document.querySelector('.chat-title');
        if (chatTitle) {
            chatTitle.textContent = 'AI Assistant';
        }
        
        // Refresh chat history
        this.loadChatHistory();
    }

    async createNewConversation() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/conversations`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ title: 'New Conversation' })
            });
            
            if (!response.ok) {
                throw new Error('Failed to create conversation');
            }
            
            const conversation = await response.json();
            this.currentChatId = conversation.id;
            
        } catch (error) {
            console.error('Error creating conversation:', error);
            // Generate a temporary ID for offline mode
            this.currentChatId = 'temp_' + Date.now();
        }
    }

    showTypingIndicator() {
        // Remove existing typing indicator
        this.removeTypingIndicator();
        
        const typingElement = document.createElement('div');
        typingElement.className = 'message assistant-message typing-message';
        typingElement.innerHTML = `
            <div class="typing-indicator">
                <span class="message-avatar">🤖</span>
                <span style="color: var(--text-secondary); font-size: 14px;">Companion is thinking</span>
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        
        this.chatMessages.appendChild(typingElement);
        this.scrollToBottom();
    }

    removeTypingIndicator() {
        const typingElement = this.chatMessages.querySelector('.typing-message');
        if (typingElement) {
            typingElement.remove();
        }
    }

    async loadChatHistory() {
        try {
            console.log('Loading chat history from:', `${this.apiBaseUrl}/conversations`);
            const response = await fetch(`${this.apiBaseUrl}/conversations`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const conversations = await response.json();
            console.log('Loaded conversations:', conversations);
            this.updateChatHistorySidebar(conversations);
            
        } catch (error) {
            console.error('Error loading chat history:', error);
            this.showEmptyHistoryState();
        }
    }

    showEmptyHistoryState() {
        const historyContainer = document.getElementById('chatHistory');
        if (!historyContainer) return;
        
        historyContainer.innerHTML = `
            <div class="empty-history">
                <div class="empty-icon">💬</div>
                <div class="empty-text">No conversations yet</div>
                <div class="empty-subtext">Start a new chat to see it here</div>
            </div>
        `;
    }

    updateChatHistorySidebar(conversations) {
        const historyContainer = document.getElementById('chatHistory');
        if (!historyContainer) return;
        
        // Clear existing content
        historyContainer.innerHTML = '';
        
        // Group conversations by time period
        const groups = [
            { title: 'Today', items: conversations.today || [] },
            { title: 'Yesterday', items: conversations.yesterday || [] },
            { title: 'Last Week', items: conversations.last_week || [] },
            { title: 'Older', items: conversations.older || [] }
        ];
        
        let hasAnyConversations = false;
        
        groups.forEach(group => {
            if (group.items.length > 0) {
                hasAnyConversations = true;
                
                // Add group header
                const header = document.createElement('div');
                header.className = 'history-group-header';
                header.textContent = group.title;
                historyContainer.appendChild(header);
                
                // Add conversations
                group.items.forEach(conv => {
                    const item = document.createElement('div');
                    item.className = 'history-item';
                    item.dataset.conversationId = conv.id;
                    
                    item.innerHTML = `
                        <span class="history-icon">💬</span>
                        <div class="history-content">
                            <span class="history-text">${conv.title}</span>
                            <span class="history-time">${this.formatDate(conv.updated_at)}</span>
                        </div>
                        <button class="history-action" title="Delete conversation">⋯</button>
                    `;
                    
                    // Add click handler for the conversation item
                    const contentArea = item.querySelector('.history-content');
                    contentArea.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.loadHistoryItem(item);
                    });
                    
                    // Add click handler for the delete button
                    const deleteBtn = item.querySelector('.history-action');
                    deleteBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.showDeleteConfirmation(conv.id, conv.title, item);
                    });
                    
                    historyContainer.appendChild(item);
                });
            }
        });
        
        // Show empty state if no conversations
        if (!hasAnyConversations) {
            this.showEmptyHistoryState();
        }
    }

    async loadHistoryItem(item) {
        // Remove active class from all items
        document.querySelectorAll('.history-item').forEach(histItem => histItem.classList.remove('active'));
        
        // Add active class to clicked item
        item.classList.add('active');
        
        // Get conversation ID from data attribute
        const conversationId = item.dataset.conversationId;
        if (!conversationId) {
            console.error('No conversation ID found');
            return;
        }
        
        this.currentChatId = conversationId;
        
        // Switch to chat view
        this.switchToChatView();
        
        // Load actual conversation from backend
        await this.loadConversation(conversationId);
        
        // Update chat title
        const chatTitle = document.querySelector('.chat-title');
        const historyText = item.querySelector('.history-text').textContent;
        if (chatTitle) {
            chatTitle.textContent = historyText;
        }
    }

    async loadConversation(conversationId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/conversations/${conversationId}/messages`);
            if (!response.ok) {
                throw new Error('Failed to load conversation');
            }
            
            const messages = await response.json();
            
            // Clear current messages
            this.chatMessages.innerHTML = '';
            
            // Add all messages
            messages.forEach(msg => {
                this.addMessage(msg.role, msg.content, msg.id);
            });
            
        } catch (error) {
            console.error('Error loading conversation:', error);
            this.chatMessages.innerHTML = '';
            this.addMessage('assistant', 'Sorry, I couldn\'t load this conversation.');
        }
    }

    showDeleteConfirmation(conversationId, title, itemElement) {
        const confirmDelete = confirm(`Are you sure you want to delete the conversation "${title}"? This action cannot be undone.`);
        
        if (confirmDelete) {
            this.deleteConversation(conversationId, itemElement);
        }
    }

    async deleteConversation(conversationId, itemElement) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/conversations/${conversationId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error('Failed to delete conversation');
            }
            
            // Remove from UI
            itemElement.remove();
            
            // If this was the current conversation, start a new chat
            if (this.currentChatId === conversationId) {
                this.startNewChat();
            }
            
            // Refresh chat history
            this.loadChatHistory();
            
        } catch (error) {
            console.error('Error deleting conversation:', error);
            alert('Failed to delete conversation. Please try again.');
        }
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        const hours = Math.floor(diff / (1000 * 60 * 60));
        
        if (hours < 1) {
            return 'Just now';
        } else if (hours < 24) {
            return `${hours}h ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    scrollToBottom() {
        if (this.chatMessages) {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }

    toggleToolsDropdown() {
        this.toolsDropdown?.classList.toggle('show');
    }

    selectTool(tool) {
        console.log(`Selected tool: ${tool}`);
        this.toolsDropdown?.classList.remove('show');
        
        // Update input placeholder based on tool
        const placeholders = {
            think: "Ask me to think deeply about...",
            research: "What would you like me to research?",
            web: "Search the web for...",
            code: "What code would you like me to write?"
        };
        
        if (this.chatInput && placeholders[tool]) {
            this.chatInput.placeholder = placeholders[tool];
        }
    }

    updateCharCount() {
        if (this.chatTextarea && this.charCount) {
            const length = this.chatTextarea.value.length;
            this.charCount.textContent = `${length}/2000`;
        }
    }

    autoResizeTextarea() {
        if (this.chatTextarea) {
            this.chatTextarea.style.height = 'auto';
            this.chatTextarea.style.height = this.chatTextarea.scrollHeight + 'px';
        }
    }
}

// Initialize the chat interface when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.chatInterface = new ModernChatInterface();
});