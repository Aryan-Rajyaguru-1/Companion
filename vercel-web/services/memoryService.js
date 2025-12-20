// services/memoryService.js
// Handle conversation memory and persistence

class MemoryService {
  constructor() {
    this.storageKey = 'companion_chat_history';
  }

  saveConversation(conversationId, messages) {
    const conversations = this.getAllConversations();
    conversations[conversationId] = {
      id: conversationId,
      messages,
      timestamp: new Date().toISOString(),
      lastUpdated: new Date().toISOString(),
    };
    localStorage.setItem(this.storageKey, JSON.stringify(conversations));
  }

  getConversation(conversationId) {
    const conversations = this.getAllConversations();
    return conversations[conversationId] || null;
  }

  getAllConversations() {
    try {
      return JSON.parse(localStorage.getItem(this.storageKey)) || {};
    } catch {
      return {};
    }
  }

  deleteConversation(conversationId) {
    const conversations = this.getAllConversations();
    delete conversations[conversationId];
    localStorage.setItem(this.storageKey, JSON.stringify(conversations));
  }

  // Future: Sync with backend
  async syncWithBackend() {
    // Implement backend sync
  }
}

export default new MemoryService();