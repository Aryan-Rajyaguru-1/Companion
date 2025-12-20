// Chat API Service
class ChatApi {
    constructor(baseUrl = '/api', apiKey = null) {
        // For development, use the API server URL
        this.baseUrl = baseUrl || 'http://localhost:8000';
        this.apiKey = apiKey || this.getApiKey();
    }

    getApiKey() {
        // Try to get from environment or local storage
        return localStorage.getItem('apiKey') || 'L2u2O6EPC1d5ep3ll1b5FSkhdQ89cwut';
    }

    async sendMessage(message, conversationId = null, options = {}) {
        const payload = {
            message: message,
            conversation_id: conversationId,
            stream: options.stream || false
        };

        const response = await this.request('/v1/chat', 'POST', payload);

        if (response.success) {
            return {
                type: response.type || 'assistant',
                agent: response.agent,
                content: response.content,
                conversationId: response.conversation_id,
                processingTime: response.processing_time
            };
        } else {
            throw new Error(response.error || 'Unknown error');
        }
    }

    async getConversationHistory(conversationId) {
        return await this.request(`/v1/conversations/${conversationId}`, 'GET');
    }

    async createConversation(title = null) {
        const payload = title ? { title } : {};
        return await this.request('/v1/conversations', 'POST', payload);
    }

    async deleteConversation(conversationId) {
        return await this.request(`/v1/conversations/${conversationId}`, 'DELETE');
    }

    async getConversations() {
        return await this.request('/v1/conversations', 'GET');
    }

    async getAgents() {
        return await this.request('/v1/agents', 'GET');
    }

    async request(endpoint, method = 'GET', data = null) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
        };

        // Add API key if available
        if (this.apiKey) {
            headers['X-API-Key'] = this.apiKey;
        }

        const config = {
            method,
            headers,
        };

        if (data) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);
            const responseData = await response.json();

            if (!response.ok) {
                throw new Error(responseData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            return {
                success: true,
                ...responseData
            };
        } catch (error) {
            console.error(`API request failed: ${method} ${url}`, error);
            return {
                success: false,
                error: error.message
            };
        }
    }
}

// Global instance
const chatApi = new ChatApi();
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

    // Streaming support
    async sendMessageStreaming(message, conversationId, onChunk, onComplete, onError) {
        const payload = {
            message: message,
            conversation_id: conversationId,
            stream: true
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