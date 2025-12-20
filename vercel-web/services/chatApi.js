// Chat API Service - Updated for Unified API v4.0.0
class ChatApi {
    constructor(baseUrl = '/api', apiKey = null) {
        // For development, use the API server URL
        this.baseUrl = baseUrl || 'http://localhost:8000';
        this.apiKey = apiKey || this.getApiKey();
    }

    getApiKey() {
        // Try to get from environment or local storage
        return localStorage.getItem('apiKey') || 'your-secret-api-key-change-this';
    }

    async sendMessage(message, conversationId = null, agent = 'companion', options = {}) {
        const payload = {
            message: message,
            conversation_id: conversationId,
            agent: agent,
            stream: false,  // Use regular endpoint for non-streaming
            max_tokens: options.maxTokens || 2048,
            temperature: options.temperature || 0.7
        };

        const response = await this.request('/chat', 'POST', payload);

        return {
            id: response.id,
            role: response.role,
            type: response.type,
            content: response.content,
            agent: response.agent,
            timestamp: response.timestamp,
            metadata: response.metadata,
            conversationId: conversationId || response.conversation_id
        };
    }

    async getConversationHistory(conversationId) {
        const response = await this.request(`/conversations/${conversationId}`, 'GET');
        return {
            conversationId: response.conversation_id,
            messages: response.messages,
            createdAt: response.created_at,
            updatedAt: response.updated_at
        };
    }

    async createConversation() {
        const response = await this.request('/conversations', 'POST', {});
        return { conversationId: response.conversation_id };
    }

    async deleteConversation(conversationId) {
        return await this.request(`/conversations/${conversationId}`, 'DELETE');
    }

    async listConversations() {
        const response = await this.request('/conversations', 'GET');
        return response.conversations || [];
    }

    async request(endpoint, method = 'GET', data = null) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            'X-API-Key': this.apiKey
        };

        const config = {
            method,
            headers
        };

        if (data) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    // Streaming support with agent selection
    async sendMessageStreaming(message, conversationId, agent = 'companion', onChunk, onComplete, onError, options = {}) {
        const payload = {
            message: message,
            conversation_id: conversationId,
            agent: agent,
            stream: true,
            max_tokens: options.maxTokens || 2048,
            temperature: options.temperature || 0.7
        };

        try {
            const response = await fetch(`${this.baseUrl}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': this.apiKey
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.type === 'done') {
                                onComplete && onComplete();
                            } else {
                                onChunk && onChunk(data);
                            }
                        } catch (e) {
                            console.error('Failed to parse streaming data:', e);
                        }
                    }
                }
            }
        } catch (error) {
            onError && onError(error);
        }
    }
}

// Global instance
const chatApi = new ChatApi();