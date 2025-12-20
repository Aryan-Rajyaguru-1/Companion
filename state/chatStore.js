// Chat State Store
class ChatStore {
    constructor() {
        this.conversations = [];
        this.currentConversationId = null;
        this.listeners = [];
    }

    // Subscribe to state changes
    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    }

    // Notify all listeners
    notify() {
        this.listeners.forEach(listener => listener(this.getState()));
    }

    // Get current state
    getState() {
        return {
            conversations: this.conversations,
            currentConversationId: this.currentConversationId,
            currentConversation: this.getCurrentConversation()
        };
    }

    // Get current conversation
    getCurrentConversation() {
        return this.conversations.find(conv => conv.id === this.currentConversationId);
    }

    // Create new conversation
    createConversation(title = 'New Chat') {
        const conversation = {
            id: this.generateId(),
            title,
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        this.conversations.unshift(conversation);
        this.currentConversationId = conversation.id;
        this.saveToStorage();
        this.notify();
        return conversation;
    }

    // Add message to current conversation
    addMessage(message) {
        const conversation = this.getCurrentConversation();
        if (!conversation) return;

        conversation.messages.push(message);
        conversation.updatedAt = new Date().toISOString();
        this.saveToStorage();
        this.notify();
    }

    // Update message (for streaming)
    updateMessage(messageId, updates) {
        const conversation = this.getCurrentConversation();
        if (!conversation) return;

        const message = conversation.messages.find(msg => msg.id === messageId);
        if (message) {
            Object.assign(message, updates);
            conversation.updatedAt = new Date().toISOString();
            this.saveToStorage();
            this.notify();
        }
    }

    // Delete conversation
    deleteConversation(conversationId) {
        this.conversations = this.conversations.filter(conv => conv.id !== conversationId);
        if (this.currentConversationId === conversationId) {
            this.currentConversationId = this.conversations[0]?.id || null;
        }
        this.saveToStorage();
        this.notify();
    }

    // Switch to conversation
    switchConversation(conversationId) {
        this.currentConversationId = conversationId;
        this.notify();
    }

    // Clear current conversation
    clearCurrentConversation() {
        const conversation = this.getCurrentConversation();
        if (conversation) {
            conversation.messages = [];
            conversation.updatedAt = new Date().toISOString();
            this.saveToStorage();
            this.notify();
        }
    }

    // Load from localStorage
    loadFromStorage() {
        try {
            const data = localStorage.getItem('chatStore');
            if (data) {
                const parsed = JSON.parse(data);
                this.conversations = parsed.conversations || [];
                this.currentConversationId = parsed.currentConversationId;
            }
        } catch (error) {
            console.error('Failed to load chat store:', error);
        }
    }

    // Save to localStorage
    saveToStorage() {
        try {
            const data = {
                conversations: this.conversations,
                currentConversationId: this.currentConversationId
            };
            localStorage.setItem('chatStore', JSON.stringify(data));
        } catch (error) {
            console.error('Failed to save chat store:', error);
        }
    }

    // Generate unique ID
    generateId() {
        return 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // Initialize store
    init() {
        this.loadFromStorage();
        if (this.conversations.length === 0) {
            this.createConversation();
        }
    }
}

// Global instance
const chatStore = new ChatStore();
chatStore.init();