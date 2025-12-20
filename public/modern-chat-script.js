// Modern Chat Interface JavaScript

class ModernChatInterface {
        // --- AUTH MANAGEMENT ---
        async checkAuthOnLoad() {
            // Check for token in storage
            const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
            if (!token) {
                this.showLoginModal();
                return false;
            }
            // Validate token with backend
            try {
                const res = await fetch(`${this.apiBaseUrl}/auth/me`, {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if (res.status === 401) {
                    this.clearAuth();
                    this.showLoginModal();
                    return false;
                }
                const data = await res.json();
                if (!data.user) {
                    this.clearAuth();
                    this.showLoginModal();
                    return false;
                }
                // Valid user
                this.currentUser = data.user;
                this.hideLoginModal();
                return true;
            } catch (e) {
                this.clearAuth();
                this.showLoginModal();
                return false;
            }
        }

        clearAuth() {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('user_data');
            sessionStorage.removeItem('auth_token');
            sessionStorage.removeItem('user_data');
            this.currentUser = null;
        }

        // Show/hide login modal (implement modal in HTML if not present)
        showLoginModal() {
            const modal = document.getElementById('loginModal');
            if (modal) modal.style.display = 'flex';
        }
        hideLoginModal() {
            const modal = document.getElementById('loginModal');
            if (modal) modal.style.display = 'none';
        }

        // Wrap fetch to auto-handle 401 and token
        async authFetch(url, options = {}) {
            const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
            options.headers = options.headers || {};
            if (token) options.headers['Authorization'] = 'Bearer ' + token;
            let response = await fetch(url, options);
            if (response.status === 401) {
                this.clearAuth();
                this.showLoginModal();
                throw new Error('Unauthorized');
            }
            return response;
        }
    constructor() {
        this.currentChatId = null;
        this.chatHistory = [];
        this.isWelcomeState = true;
        this.apiBaseUrl = `${window.location.protocol}//${window.location.host}/api`;
        this.activeTools = new Set(); // Track active tools
        
        this.initializeElements();
        this.bindEvents();
        // --- AUTH: Check on load ---
        this.checkAuthOnLoad().then((authed) => {
            if (authed) {
                this.loadChatHistory();
            }
        });
        this.initializeToolToggles();
        this.setupFileUpload(); // Initialize file upload functionality
        this.initializeSearch(); // Initialize search functionality
        this.initializeMobileMenu(); // Initialize mobile menu
        this.initializeVoiceChat(); // Initialize voice chat functionality
        this.fixMainSearchDropdown(); // Fix main search bar dropdown
        // Initial height adjustment and window resize handler
        setTimeout(() => this.adjustChatAreaHeight(), 100);
        window.addEventListener('resize', () => this.adjustChatAreaHeight());
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
        
        // Tool toggles
        this.activeToolsContainer = document.getElementById('activeTools');
        this.activeToolsList = document.getElementById('activeToolsList');
        this.toolCheckboxes = document.querySelectorAll('.tool-checkbox');
        
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
        
        // Chat area tools button
        const toolsBtnChat = document.getElementById('toolsBtnChat');
        if (toolsBtnChat) {
            toolsBtnChat.addEventListener('click', () => this.toggleChatToolsPanel());
        }
        
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
            // Close tools dropdowns
            if (!e.target.closest('.tools-dropdown') && !e.target.closest('.tools-btn') && !e.target.closest('.tools-btn-chat')) {
                this.toolsDropdown?.classList.remove('show');
                const toolsDropdownChat = document.getElementById('toolsDropdownChat');
                if (toolsDropdownChat) toolsDropdownChat.style.display = 'none';
            }
            
            // Close add dropdowns
            if (!e.target.closest('.add-dropdown') && !e.target.closest('.add-btn')) {
                const addDropdown = document.getElementById('addDropdown');
                const addDropdownMain = document.getElementById('addDropdownMain');
                if (addDropdown) addDropdown.style.display = 'none';
                if (addDropdownMain) addDropdownMain.style.display = 'none';
            }
            
            // Close conversation dropdowns when clicking outside
            if (!e.target.closest('.history-action-container')) {
                document.querySelectorAll('.conversation-dropdown.show').forEach(dd => {
                    dd.classList.remove('show');
                });
            }
            
            // Handle logout button
            if (e.target.classList.contains('logout') || e.target.closest('.logout')) {
                e.preventDefault();
                this.clearAuth();
                window.location.href = '/login.html';
            }
            
            // Handle logout clicks
            if (e.target.classList.contains('logout') || e.target.closest('.logout')) {
                e.preventDefault();
                this.clearAuth();
                window.location.href = 'login.html';
            }
        });
        
        // Auto-resize textarea
        if (this.chatTextarea) {
            this.chatTextarea.addEventListener('input', () => this.autoResizeTextarea());
        }
    }

    initializeToolToggles() {
        // Add event listeners for tool toggles - only allow ONE tool at a time
        this.toolCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const tool = e.target.dataset.tool;
                if (e.target.checked) {
                    // Clear all other tools first (only allow one tool)
                    this.activeTools.clear();
                    // Uncheck all other checkboxes
                    this.toolCheckboxes.forEach(cb => {
                        if (cb !== e.target) {
                            cb.checked = false;
                        }
                    });
                    // Add the selected tool
                    this.activeTools.add(tool);
                } else {
                    this.activeTools.delete(tool);
                }
                this.updateActiveToolsDisplay();
            });
        });
    }

    updateActiveToolsDisplay() {
        if (this.activeTools.size > 0) {
            this.activeToolsContainer.style.display = 'flex';
            this.activeToolsList.innerHTML = Array.from(this.activeTools).map(tool => {
                const toolNames = {
                    'search': '🔍 Search',
                    'deepsearch': '� Deep Search',
                    'agent': '🤖 Agent Mode'
                };
                return `<span class="active-tool">${toolNames[tool] || tool}</span>`;
            }).join('');
        } else {
            this.activeToolsContainer.style.display = 'none';
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
        // Collect active tools from checkboxes
        const activeTools = Array.from(document.querySelectorAll('.tool-checkbox:checked')).map(cb => cb.dataset.tool);

        // Show progress bar for tool operations
        if (activeTools.length > 0) {
            this.showProgressBar(activeTools[0]); // Show progress for the first active tool
        }
        
        // Send message to backend (with auth, 401 auto-handling)
        const response = await this.authFetch(`${this.apiBaseUrl}/conversations/${this.currentChatId}/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                message: message,
                tools: activeTools  // Include selected tools
            })
        });
        if (!response.ok) {
            throw new Error('Failed to send message');
        }
        const data = await response.json();
        
        // Hide progress bar
        this.hideProgressBar();
        
        // Remove typing indicator
        this.removeTypingIndicator();
            
            // Add AI response with learned status and thinking data if available
            const thinkingData = data.assistant_message.thinking || null;
            this.addMessage('assistant', data.assistant_message.content, data.message_id, data.is_learned || false, thinkingData);
            
            // Update chat history sidebar
            this.loadChatHistory();
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.hideProgressBar(); // Hide progress bar on error
            this.removeTypingIndicator();
            this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        }
    }

    addMessage(type, content, messageId = null, isLearned = false, thinkingData = null) {
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
                        <button class="message-edit-btn" onclick="window.chatInterface.editQueryMessage('${messageElement.dataset.messageId}', \`${content.replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`)" title="Edit and resend">
                            <img src="/SVGs/edit.svg" alt="Edit" style="width: 16px; height: 16px;">
                        </button>
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
                        <img src="Logo.png" alt="Companion" class="message-avatar companion-logo">
                        <span class="message-sender">Companion</span>
                        <span class="message-time">${time}</span>
                        <button class="show-thinking-btn" title="Show thinking process" style="display: ${thinkingData ? 'flex' : 'none'};">
                            <span>🧠</span>
                            <span class="btn-text">Show thinking</span>
                        </button>
                    </div>
                    <div class="message-content">
                        ${this.formatMessage(content)}
                    </div>
                    <div class="thinking-process" style="display: none;">
                        <div class="thinking-header">
                            <span class="thinking-icon">🧠</span>
                            <span class="thinking-title">Thinking Process</span>
                            <button class="collapse-thinking-btn" title="Hide thinking">
                                <span>▼</span>
                            </button>
                        </div>
                        <div class="thinking-content">
                            ${thinkingData || 'No thinking process available for this response.'}
                        </div>
                    </div>
                    <div class="message-footer">
                        <div class="message-status">
                            ${isLearned ? '<span class="status-icon status-learned">◉</span><span>Adaptive Response</span>' : ''}
                        </div>
                        <div class="message-actions-row">
                            <button class="msg-action-btn" data-action="copy" title="Copy response">
                                <img src="/SVGs/copy.svg" alt="Copy" class="action-icon">
                                <span class="btn-text">Copy</span>
                            </button>
                            <button class="msg-action-btn" data-action="read-aloud" title="Read aloud">
                                <img src="/SVGs/speak aloud.svg" alt="Read aloud" class="action-icon">
                                <span class="btn-text">Read aloud</span>
                            </button>
                            <button class="msg-action-btn" data-action="regenerate" title="Regenerate response">
                                <img src="/SVGs/regenerate response_1.svg" alt="Regenerate" class="action-icon">
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
        
        // Ensure proper height adjustment
        this.adjustChatAreaHeight();
        
        // Scroll to bottom after a short delay to ensure content is rendered
        setTimeout(() => {
            this.scrollToBottom();
        }, 100);
        
        // Add event listeners for assistant messages
        if (type === 'assistant') {
            this.setupMessageEventListeners(messageElement, content);
            
            // Set up thinking button if thinking data is available
            if (thinkingData) {
                const showThinkingBtn = messageElement.querySelector('.show-thinking-btn');
                if (showThinkingBtn) {
                    showThinkingBtn.addEventListener('click', () => {
                        this.toggleThinkingProcess(messageElement);
                    });
                }
            }
        }
    }

    generateMessageId() {
        return 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    toggleThinkingProcess(messageElement) {
        const thinkingProcess = messageElement.querySelector('.thinking-process');
        const showThinkingBtn = messageElement.querySelector('.show-thinking-btn');
        
        if (thinkingProcess && showThinkingBtn) {
            const isVisible = thinkingProcess.style.display === 'block';
            thinkingProcess.style.display = isVisible ? 'none' : 'block';
            showThinkingBtn.textContent = isVisible ? 'Show thinking' : 'Hide thinking';
        }
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
        
        // Code copy button listeners
        const copyBtns = messageElement.querySelectorAll('.copy-btn[data-code-id]');
        copyBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const codeId = btn.getAttribute('data-code-id');
                this.copyCodeToClipboard(codeId, btn);
            });
        });
    }

    formatMessage(content) {
        // Check if this is a web search result and format it specially
        if (content.includes('🌐 **Web Search Results:**') || content.includes('🌐 **Deep Research Results:**')) {
            return this.formatWebSearchResults(content);
        }
        
        // More comprehensive HTML entity and tag cleanup
        let processedContent = content
            // First handle line breaks
            .replace(/<br\s*\/?>/gi, '\n')
            .replace(/<\/p>/gi, '\n')
            .replace(/<p>/gi, '')
            // Then decode all HTML entities comprehensively
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&amp;/g, '&')
            .replace(/&quot;/g, '"')
            .replace(/&#39;/g, "'")
            .replace(/&#x27;/g, "'")
            .replace(/&#x2F;/g, '/')
            .replace(/&nbsp;/g, ' ')
            .replace(/&apos;/g, "'")
            .replace(/&lpar;/g, '(')
            .replace(/&rpar;/g, ')')
            .replace(/&lsqb;/g, '[')
            .replace(/&rsqb;/g, ']')
            .replace(/&lcub;/g, '{')
            .replace(/&rcub;/g, '}')
            .replace(/&sol;/g, '/')
            .replace(/&bsol;/g, '\\')
            .replace(/&lowbar;/g, '_')
            .replace(/&ast;/g, '*')
            .replace(/&plus;/g, '+')
            .replace(/&equals;/g, '=')
            .replace(/&dollar;/g, '$')
            .replace(/&percnt;/g, '%')
            .replace(/&num;/g, '#')
            .replace(/&commat;/g, '@')
            .replace(/&excl;/g, '!')
            .replace(/&quest;/g, '?')
            // Handle numeric HTML entities
            .replace(/&#(\d+);/g, (match, dec) => String.fromCharCode(parseInt(dec, 10)))
            .replace(/&#x([0-9A-Fa-f]+);/g, (match, hex) => String.fromCharCode(parseInt(hex, 16)))
            // Remove any remaining HTML tags that might interfere
            .replace(/<\/?em>/gi, '*')
            .replace(/<\/?strong>/gi, '**')
            .replace(/<\/?i>/gi, '*')
            .replace(/<\/?b>/gi, '**');
        
        // Process code blocks first (including multiline code blocks)
        let formatted = this.processCodeBlocks(processedContent);
        
        // Basic markdown-like formatting with clickable links
        formatted = formatted
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            // Make URLs clickable - handle various URL formats
            .replace(/https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?]/g, (url) => {
                return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="chat-link">${url}</a>`;
            })
            // Handle numbered reference links (like "1. **Title**\n   🔗 URL")
            .replace(/🔗\s*(https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?])/g, (match, url) => {
                return `🔗 <a href="${url}" target="_blank" rel="noopener noreferrer" class="chat-link">${url}</a>`;
            })
            .replace(/\n/g, '<br>');
            
        return formatted;
    }

    formatWebSearchResults(content) {
        // Enhanced web search result formatting
        // First, convert any <br> tags back to newlines for proper processing
        // Also handle HTML entities that might be present
        let formattedContent = content
            .replace(/<br\s*\/?>/gi, '\n');
        formattedContent = this.decodeHtmlEntities(formattedContent);
        
        // Format the main headers
        formattedContent = formattedContent
            .replace(/🌐 \*\*(.*?)\*\*:/g, '<div class="search-header">🌐 <strong>$1</strong></div>')
            .replace(/📖 \*\*(.*?)\*\*:/g, '<div class="search-summary-header">📖 <strong>$1</strong></div>')
            .replace(/💡 \*\*(.*?)\*\*:/g, '<div class="search-facts-header">💡 <strong>$1</strong></div>')
            .replace(/🔍 \*\*(.*?)\*\*:/g, '<div class="search-results-header">🔍 <strong>$1</strong></div>')
            .replace(/🔗 \*\*(.*?)\*\*:/g, '<div class="search-related-header">🔗 <strong>$1</strong></div>')
            .replace(/ℹ️ \*\*(.*?)\*\*:/g, '<div class="search-note-header">ℹ️ <strong>$1</strong></div>');
        
        // Format individual search results with better structure
        formattedContent = formattedContent.replace(
            /(\d+)\.\s+\*\*(.*?)\*\*\s+\(via\s+(.*?)\)\s*\n\s*📝\s+(.*?)(?=\n\n|\n\d+\.|\n🔗|\n💡|\n📄|$)/gs,
            (match, num, title, source, snippet) => {
                return `<div class="search-result-item">
                    <div class="result-title"><strong>${num}. ${title}</strong> <span class="result-source">(via ${source})</span></div>
                    <div class="result-snippet">📝 ${snippet}</div>
                </div>`;
            }
        );
        
        // Format key facts as a clean list
        formattedContent = formattedContent.replace(
            /(\d+)\.\s+([^0-9\n]+)(?=\n\d+\.|\n\n|\n🔍|\n🔗|$)/g,
            '<div class="fact-item"><span class="fact-number">$1.</span> <span class="fact-text">$2</span></div>'
        );
        
        // Format related topics as a clean list
        formattedContent = formattedContent.replace(
            /•\s+([^\n]+)/g,
            '<div class="topic-item">• $1</div>'
        );
        
        // Process code blocks that might be in search results
        formattedContent = this.processCodeBlocks(formattedContent);
        
        // Apply basic markdown formatting
        formattedContent = formattedContent
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>');
        
        // Make URLs clickable
        formattedContent = formattedContent
            .replace(/https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?]/g, (url) => {
                return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="chat-link">${url}</a>`;
            })
            .replace(/🔗\s*(https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?])/g, (match, url) => {
                return `🔗 <a href="${url}" target="_blank" rel="noopener noreferrer" class="chat-link">${url}</a>`;
            });
        
        // Convert line breaks
        formattedContent = formattedContent.replace(/\n/g, '<br>');
        
        return formattedContent;
    }

    decodeHtmlEntities(text) {
        // Comprehensive HTML entity decoding
        return text
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&amp;/g, '&')
            .replace(/&quot;/g, '"')
            .replace(/&#39;/g, "'")
            .replace(/&#x27;/g, "'")
            .replace(/&#x2F;/g, '/')
            .replace(/&nbsp;/g, ' ')
            .replace(/&apos;/g, "'")
            .replace(/&lpar;/g, '(')
            .replace(/&rpar;/g, ')')
            .replace(/&lsqb;/g, '[')
            .replace(/&rsqb;/g, ']')
            .replace(/&lcub;/g, '{')
            .replace(/&rcub;/g, '}')
            .replace(/&sol;/g, '/')
            .replace(/&bsol;/g, '\\')
            .replace(/&lowbar;/g, '_')
            .replace(/&ast;/g, '*')
            .replace(/&plus;/g, '+')
            .replace(/&equals;/g, '=')
            .replace(/&dollar;/g, '$')
            .replace(/&percnt;/g, '%')
            .replace(/&num;/g, '#')
            .replace(/&commat;/g, '@')
            .replace(/&excl;/g, '!')
            .replace(/&quest;/g, '?')
            // Handle numeric HTML entities
            .replace(/&#(\d+);/g, (match, dec) => String.fromCharCode(parseInt(dec, 10)))
            .replace(/&#x([0-9A-Fa-f]+);/g, (match, hex) => String.fromCharCode(parseInt(hex, 16)));
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
                this.copyToClipboard(content).then(success => {
                    if (success) {
                        this.showTemporaryStatus(messageElement, 'Copied to clipboard!', 'success');
                        
                        // Debug: Log what was copied for troubleshooting
                        console.log('Original content:', content);
                        const tempDiv = document.createElement('div');
                        tempDiv.innerHTML = content;
                        const cleaned = tempDiv.textContent || tempDiv.innerText || '';
                        console.log('Cleaned content:', cleaned);
                    } else {
                        this.showTemporaryStatus(messageElement, 'Failed to copy text', 'error');
                    }
                });
                break;
                
            case 'read-aloud':
                this.readAloud(content, messageElement);
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
            // First pass: Clean the text from HTML tags and entities
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = text;
            let cleanText = tempDiv.textContent || tempDiv.innerText || '';
            
            // Second pass: More aggressive cleanup for better formatting
            cleanText = cleanText
                // Fix line breaks and spacing
                .replace(/\s+/g, ' ')           // Multiple spaces to single space
                .replace(/\n\s+/g, '\n')        // Remove spaces after newlines
                .replace(/\s+\n/g, '\n')        // Remove spaces before newlines
                .replace(/\n{3,}/g, '\n\n')     // Multiple newlines to double newline
                // Clean up any remaining HTML entities that might have been missed
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/&amp;/g, '&')
                .replace(/&quot;/g, '"')
                .replace(/&#39;/g, "'")
                .replace(/&#x27;/g, "'")
                .replace(/&#x2F;/g, '/')
                .replace(/&nbsp;/g, ' ')
                .replace(/&apos;/g, "'")
                .replace(/&lpar;/g, '(')
                .replace(/&rpar;/g, ')')
                .replace(/&lsqb;/g, '[')
                .replace(/&rsqb;/g, ']')
                .replace(/&lcub;/g, '{')
                .replace(/&rcub;/g, '}')
                .replace(/&sol;/g, '/')
                .replace(/&bsol;/g, '\\')
                .replace(/&lowbar;/g, '_')
                .replace(/&ast;/g, '*')
                .replace(/&plus;/g, '+')
                .replace(/&equals;/g, '=')
                .replace(/&dollar;/g, '$')
                .replace(/&percnt;/g, '%')
                .replace(/&num;/g, '#')
                .replace(/&commat;/g, '@')
                .replace(/&excl;/g, '!')
                .replace(/&quest;/g, '?')
                // Handle numeric HTML entities
                .replace(/&#(\d+);/g, (match, dec) => String.fromCharCode(parseInt(dec, 10)))
                .replace(/&#x([0-9A-Fa-f]+);/g, (match, hex) => String.fromCharCode(parseInt(hex, 16)))
                // Remove any leftover HTML-like patterns
                .replace(/<br\s*\/?>/gi, '\n')
                .replace(/<[^>]*>/g, '')
                .trim();
            
            // Third pass: Create a new temp element to ensure complete HTML cleanup
            const tempDiv2 = document.createElement('div');
            tempDiv2.textContent = cleanText;
            const finalCleanText = tempDiv2.textContent || tempDiv2.innerText || cleanText;
            
            await navigator.clipboard.writeText(finalCleanText);
            return true;
        } catch (err) {
            console.error('Failed to copy text:', err);
            
            // Fallback method for older browsers with same cleaning logic
            try {
                // Apply the same comprehensive cleaning for fallback
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = text;
                let cleanText = tempDiv.textContent || tempDiv.innerText || '';
                
                cleanText = cleanText
                    .replace(/\s+/g, ' ')
                    .replace(/\n\s+/g, '\n')
                    .replace(/\s+\n/g, '\n')
                    .replace(/\n{3,}/g, '\n\n')
                    .replace(/&lt;/g, '<')
                    .replace(/&gt;/g, '>')
                    .replace(/&amp;/g, '&')
                    .replace(/&quot;/g, '"')
                    .replace(/&#39;/g, "'")
                    .replace(/&#x27;/g, "'")
                    .replace(/&#x2F;/g, '/')
                    .replace(/&nbsp;/g, ' ')
                    .replace(/&apos;/g, "'")
                    .replace(/&lpar;/g, '(')
                    .replace(/&rpar;/g, ')')
                    .replace(/&lsqb;/g, '[')
                    .replace(/&rsqb;/g, ']')
                    .replace(/&lcub;/g, '{')
                    .replace(/&rcub;/g, '}')
                    .replace(/&sol;/g, '/')
                    .replace(/&bsol;/g, '\\')
                    .replace(/&lowbar;/g, '_')
                    .replace(/&ast;/g, '*')
                    .replace(/&plus;/g, '+')
                    .replace(/&equals;/g, '=')
                    .replace(/&dollar;/g, '$')
                    .replace(/&percnt;/g, '%')
                    .replace(/&num;/g, '#')
                    .replace(/&commat;/g, '@')
                    .replace(/&excl;/g, '!')
                    .replace(/&quest;/g, '?')
                    .replace(/&#(\d+);/g, (match, dec) => String.fromCharCode(parseInt(dec, 10)))
                    .replace(/&#x([0-9A-Fa-f]+);/g, (match, hex) => String.fromCharCode(parseInt(hex, 16)))
                    .replace(/<br\s*\/?>/gi, '\n')
                    .replace(/<[^>]*>/g, '')
                    .trim();
                
                const tempDiv2 = document.createElement('div');
                tempDiv2.textContent = cleanText;
                const finalCleanText = tempDiv2.textContent || tempDiv2.innerText || cleanText;
                
                const textArea = document.createElement('textarea');
                textArea.value = finalCleanText;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                return true;
            } catch (fallbackErr) {
                console.error('Fallback copy failed:', fallbackErr);
                return false;
            }
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
        
        // Adjust chat area height for input area
        this.adjustChatAreaHeight();
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
        
        // Reset chat area height
        this.adjustChatAreaHeight();
        
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
        
        // Determine the correct status message based on active tools
        let statusMessage = 'Companion is thinking';
        
        if (this.activeTools.has('deepthink')) {
            statusMessage = 'Companion is analyzing with all AI models and search engines';
        } else if (this.activeTools.has('web')) {
            statusMessage = 'Companion is searching';
        } else if (this.activeTools.has('research') || this.activeTools.has('deepsearch')) {
            statusMessage = 'Companion is researching';
        } else if (this.activeTools.has('think')) {
            statusMessage = 'Companion is thinking deeply';
        } else if (this.activeTools.has('code')) {
            statusMessage = 'Companion is coding';
        }
        
        const typingElement = document.createElement('div');
        typingElement.className = 'message assistant-message typing-message';
        typingElement.innerHTML = `
            <div class="typing-indicator">
                <img src="Logo.png" alt="Companion" class="message-avatar companion-logo">
                <span style="color: var(--text-secondary); font-size: 14px;">${statusMessage}</span>
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

    // Progress Bar Methods
    showProgressBar(tool) {
        const progressContainer = document.getElementById('progressContainer');
        const progressText = document.getElementById('progressText');
        const progressFill = document.getElementById('progressFill');

        if (!progressContainer) return;

        // Set tool-specific text and styling
        let toolName = 'AI';
        let estimatedTime = '30-60 seconds';
        let statusMessage = 'Initializing...';

        switch(tool) {
            case 'search':
                toolName = 'Quick Search';
                estimatedTime = '20-25 seconds';
                statusMessage = 'Searching with optimized AI models...';
                progressFill.className = 'progress-fill search';
                break;
            case 'deepsearch':
                toolName = 'Deep Research';
                estimatedTime = '60-80 seconds';
                statusMessage = 'Analyzing with advanced reasoning...';
                progressFill.className = 'progress-fill deepsearch';
                break;
            case 'agent':
                toolName = 'Agent Mode';
                estimatedTime = '60-80 seconds';
                statusMessage = 'Activating autonomous AI assistance...';
                progressFill.className = 'progress-fill agent';
                break;
            default:
                progressFill.className = 'progress-fill';
        }

        progressText.textContent = `${statusMessage} (~${estimatedTime})`;
        progressContainer.style.display = 'block';

        // Reset progress
        progressFill.style.width = '0%';
        document.getElementById('progressPercent').textContent = '0%';

        // Start progress animation with status updates
        this.startProgressAnimation(tool);
    }

    hideProgressBar() {
        const progressContainer = document.getElementById('progressContainer');
        if (progressContainer) {
            progressContainer.style.display = 'none';
        }
        this.stopProgressAnimation();
    }

    startProgressAnimation(tool) {
        this.progressInterval = setInterval(() => {
            const progressFill = document.getElementById('progressFill');
            const progressPercent = document.getElementById('progressPercent');
            const progressText = document.getElementById('progressText');

            if (!progressFill) return;

            let currentWidth = parseFloat(progressFill.style.width) || 0;
            let increment = 0;
            let statusUpdate = '';

            // Different progress speeds and status updates for different tools
            switch(tool) {
                case 'search':
                    increment = Math.random() * 3 + 1; // Faster for search
                    if (currentWidth < 30) statusUpdate = 'Searching with optimized AI models...';
                    else if (currentWidth < 70) statusUpdate = 'Processing results...';
                    else statusUpdate = 'Finalizing response...';
                    break;
                case 'deepsearch':
                case 'agent':
                    increment = Math.random() * 1.5 + 0.5; // Slower for complex tasks
                    if (currentWidth < 20) statusUpdate = 'Analyzing with advanced reasoning...';
                    else if (currentWidth < 50) statusUpdate = 'Exploring multiple perspectives...';
                    else if (currentWidth < 75) statusUpdate = 'Synthesizing information...';
                    else statusUpdate = 'Generating comprehensive response...';
                    break;
                default:
                    increment = Math.random() * 2 + 0.5;
            }

            currentWidth = Math.min(currentWidth + increment, 95); // Cap at 95%
            progressFill.style.width = currentWidth + '%';
            progressPercent.textContent = Math.round(currentWidth) + '%';

            // Update status text if we have a new message
            if (statusUpdate && progressText) {
                const currentText = progressText.textContent;
                const timeMatch = currentText.match(/\(~[\d-]+ seconds\)/);
                const timePart = timeMatch ? timeMatch[0] : '';
                progressText.textContent = `${statusUpdate} ${timePart}`;
            }

        }, 800); // Slightly slower updates for better UX
    }

    stopProgressAnimation() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }

        // Complete the progress bar with animation
        const progressFill = document.getElementById('progressFill');
        const progressPercent = document.getElementById('progressPercent');
        const progressText = document.getElementById('progressText');

        if (progressFill && progressPercent) {
            // Animate to 100%
            progressFill.style.width = '100%';
            progressPercent.textContent = '100%';

            // Update status to completion
            if (progressText) {
                progressText.textContent = '✅ Response complete!';
                progressText.style.color = 'var(--success-color)';
            }

            // Add completion animation
            progressFill.style.animation = 'progressComplete 0.6s ease-out';

            // Hide after completion celebration
            setTimeout(() => {
                this.hideProgressBar();
                // Reset text color
                if (progressText) {
                    progressText.style.color = '';
                }
            }, 1500);
        }
    }

    async loadChatHistory() {
        try {
            const response = await this.authFetch(`${this.apiBaseUrl}/conversations`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const conversations = await response.json();
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
                        <div class="history-action-container">
                            <button class="history-action" title="More options">⋯</button>
                            <div class="conversation-dropdown">
                                <button class="dropdown-item" data-action="rename">
                                    <span>✏️</span> Rename
                                </button>
                                <button class="dropdown-item" data-action="delete">
                                    <span>🗑️</span> Delete
                                </button>
                            </div>
                        </div>
                    `;
                    
                    // Add click handler for the conversation item
                    const contentArea = item.querySelector('.history-content');
                    contentArea.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.loadHistoryItem(item);
                    });
                    
                    // Add click handler for the action menu button
                    const actionBtn = item.querySelector('.history-action');
                    const dropdown = item.querySelector('.conversation-dropdown');
                    
                    actionBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        // Close other open dropdowns
                        document.querySelectorAll('.conversation-dropdown.show').forEach(dd => {
                            dd.classList.remove('show');
                        });
                        // Toggle current dropdown
                        dropdown.classList.toggle('show');
                    });
                    
                    // Add handlers for dropdown items
                    const renameBtn = item.querySelector('[data-action="rename"]');
                    const deleteBtn = item.querySelector('[data-action="delete"]');
                    
                    renameBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        dropdown.classList.remove('show');
                        this.showRenameDialog(conv.id, conv.title, item);
                    });
                    
                    deleteBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        dropdown.classList.remove('show');
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
        
        // Ensure proper layout after loading
        setTimeout(() => this.adjustChatAreaHeight(), 100);
    }

    async loadConversation(conversationId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/conversations/${conversationId}/messages`);
            if (!response.ok) {
                throw new Error('Failed to load conversation');
            }
            
            const data = await response.json();
            const messages = data.messages || [];
            
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

    showRenameDialog(conversationId, currentTitle, itemElement) {
        const newTitle = prompt(`Rename conversation:`, currentTitle);
        if (newTitle && newTitle.trim() && newTitle.trim() !== currentTitle) {
            this.renameConversation(conversationId, newTitle.trim(), itemElement);
        }
    }

    async renameConversation(conversationId, newTitle, itemElement) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/conversations/${conversationId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ title: newTitle })
            });

            if (!response.ok) {
                throw new Error('Failed to rename conversation');
            }

            // Update the title in the UI immediately
            const titleElement = itemElement.querySelector('.history-text');
            if (titleElement) {
                titleElement.textContent = newTitle;
            }

            // Refresh the chat history to ensure consistency
            this.loadChatHistory();

        } catch (error) {
            console.error('Error renaming conversation:', error);
            alert('Failed to rename conversation. Please try again.');
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
        // Ensure UTC parsing: if no 'Z' or timezone, add 'Z'
        let safeDateString = dateString;
        if (typeof safeDateString === 'string' && !safeDateString.match(/[zZ]|[+-]\d{2}:?\d{2}$/)) {
            safeDateString += 'Z';
        }
        const date = new Date(safeDateString);
        const now = new Date();
        const diff = now - date;
        const minutes = Math.floor(diff / (1000 * 60));
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));

        if (minutes < 1) {
            return 'Just now';
        } else if (minutes < 60) {
            return `${minutes}m ago`;
        } else if (hours < 24) {
            return `${hours}h ago`;
        } else if (days < 7) {
            return `${days}d ago`;
        } else {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        }
    }

    adjustChatAreaHeight() {
        const chatArea = document.querySelector('.chat-area');
        const chatMessages = document.querySelector('.chat-messages');
        const inputArea = document.getElementById('inputArea');
        const topBar = document.querySelector('.top-bar');
        
        if (chatArea && chatMessages && inputArea && topBar) {
            const topBarHeight = topBar.offsetHeight;
            const inputAreaHeight = inputArea.style.display !== 'none' ? inputArea.offsetHeight : 0;
            
            // Calculate available height for chat messages
            const availableHeight = window.innerHeight - topBarHeight - inputAreaHeight - 40; // 40px for margins
            
            // Update chat messages max height
            chatMessages.style.maxHeight = `${availableHeight}px`;
            
            console.log('Height calculation:', {
                windowHeight: window.innerHeight,
                topBarHeight,
                inputAreaHeight,
                availableHeight
            });
        }
    }

    scrollToBottom() {
        if (this.chatMessages) {
            // Use requestAnimationFrame for smooth scrolling and ensure it reaches the bottom
            requestAnimationFrame(() => {
                // Scroll to the very bottom with extra margin
                this.chatMessages.scrollTop = this.chatMessages.scrollHeight + 50;
                
                // Double-check with another frame to ensure complete scroll
                requestAnimationFrame(() => {
                    this.chatMessages.scrollTop = this.chatMessages.scrollHeight + 50;
                });
            });
        }
    }

    toggleToolsDropdown() {
        if (this.toolsDropdown && this.toolsBtn) {
            const isVisible = this.toolsDropdown.classList.contains('show');
            
            if (isVisible) {
                this.toolsDropdown.classList.remove('show');
            } else {
                this.toolsDropdown.classList.add('show');
                
                // Position dropdown below and aligned to right of Tools button
                const btnRect = this.toolsBtn.getBoundingClientRect();
                this.toolsDropdown.style.position = 'fixed';
                this.toolsDropdown.style.top = (btnRect.bottom + 5) + 'px';
                this.toolsDropdown.style.right = (window.innerWidth - btnRect.right) + 'px';
                this.toolsDropdown.style.left = 'auto';
                this.toolsDropdown.style.zIndex = '10000';
            }
        }
    }

    toggleChatToolsPanel() {
        const toolsDropdownChat = document.getElementById('toolsDropdownChat');
        const toolsBtnChat = document.getElementById('toolsBtnChat');
        
        if (toolsDropdownChat && toolsBtnChat) {
            const isVisible = toolsDropdownChat.style.display === 'block';
            toolsDropdownChat.style.display = isVisible ? 'none' : 'block';
            
            // Position dropdown below the Tools button - align to right edge
            if (!isVisible) {
                const btnRect = toolsBtnChat.getBoundingClientRect();
                toolsDropdownChat.style.position = 'fixed';
                toolsDropdownChat.style.top = (btnRect.bottom + 5) + 'px';
                toolsDropdownChat.style.right = (window.innerWidth - btnRect.right) + 'px';
                toolsDropdownChat.style.left = 'auto';
                toolsDropdownChat.style.zIndex = '10000';
            }
            
            console.log('🔧 Chat tools dropdown toggled:', !isVisible);
        }
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

    async readAloud(text, messageElement) {
        try {
            // Check if speech synthesis is supported
            if (!('speechSynthesis' in window)) {
                this.showTemporaryStatus(messageElement, 'Text-to-speech not supported in your browser', 'error');
                return;
            }
            
            const readBtn = messageElement.querySelector('[data-action="read-aloud"]');
            const originalText = readBtn.querySelector('.btn-text').textContent;
            
            // Check if currently speaking - if so, stop it
            if (window.speechSynthesis.speaking) {
                window.speechSynthesis.cancel();
                readBtn.querySelector('.btn-text').textContent = originalText;
                readBtn.classList.remove('active');
                this.showTemporaryStatus(messageElement, 'Stopped reading', 'info');
                return;
            }
            
            // Clean the text (remove HTML tags and format for speech)
            const cleanText = text
                .replace(/<[^>]*>/g, '') // Remove HTML tags
                .replace(/```[\s\S]*?```/g, ' code block ') // Replace code blocks
                .replace(/`([^`]+)`/g, '$1') // Remove inline code formatting
                .replace(/\*\*([^*]+)\*\*/g, '$1') // Remove bold formatting
                .replace(/\*([^*]+)\*/g, '$1') // Remove italic formatting
                .trim();
            
            if (!cleanText) {
                this.showTemporaryStatus(messageElement, 'No text to read', 'error');
                return;
            }
            
            // Create speech utterance
            const utterance = new SpeechSynthesisUtterance(cleanText);
            
            // Configure speech settings
            utterance.rate = 0.9; // Slightly slower for better comprehension
            utterance.pitch = 1.0;
            utterance.volume = 0.8;
            
            // Try to use a natural-sounding voice
            const voices = window.speechSynthesis.getVoices();
            const preferredVoice = voices.find(voice => 
                voice.lang.startsWith('en') && 
                (voice.name.includes('Natural') || voice.name.includes('Neural') || voice.name.includes('Premium'))
            ) || voices.find(voice => voice.lang.startsWith('en')) || voices[0];
            
            if (preferredVoice) {
                utterance.voice = preferredVoice;
            }
            
            // Show speaking state
            readBtn.querySelector('.btn-text').textContent = 'Stop';
            readBtn.classList.add('active');
            
            // Handle speech events
            utterance.onstart = () => {
                this.showTemporaryStatus(messageElement, 'Reading response aloud...', 'info');
            };
            
            utterance.onend = () => {
                // Reset button state
                readBtn.querySelector('.btn-text').textContent = originalText;
                readBtn.classList.remove('active');
                this.showTemporaryStatus(messageElement, 'Finished reading', 'success');
            };
            
            utterance.onerror = (event) => {
                console.error('Speech synthesis error:', event);
                // Reset button state
                readBtn.querySelector('.btn-text').textContent = originalText;
                readBtn.classList.remove('active');
                this.showTemporaryStatus(messageElement, 'Error reading text', 'error');
            };
            
            // Start speaking
            window.speechSynthesis.speak(utterance);
            
        } catch (error) {
            console.error('Error with text-to-speech:', error);
            this.showTemporaryStatus(messageElement, 'Failed to read text aloud', 'error');
        }
    }

    async regenerateResponse(messageElement) {
        try {
            // Get the last user message to regenerate response for
            const messages = this.chatMessages.querySelectorAll('.user-message');
            if (messages.length === 0) {
                this.showTemporaryStatus(messageElement, 'No message to regenerate', 'error');
                return;
            }
            
            const lastUserMessage = messages[messages.length - 1];
            const userContent = lastUserMessage.querySelector('.message-content').textContent.trim();
            
            // Remove the current AI response
            messageElement.remove();
            
            // Show typing indicator
            this.showTypingIndicator();
            
            // Send the same message again to get a new response
            const response = await fetch(`${this.apiBaseUrl}/conversations/${this.currentChatId}/messages`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: userContent })
            });
            
            if (!response.ok) {
                throw new Error('Failed to regenerate response');
            }
            
            const data = await response.json();
            
            // Remove typing indicator
            this.removeTypingIndicator();
            
            // Add new AI response with thinking data if available
            const thinkingData = data.assistant_message.thinking || null;
            this.addMessage('assistant', data.assistant_message.content, data.message_id, data.is_learned || false, thinkingData);
            
        } catch (error) {
            console.error('Error regenerating response:', error);
            this.removeTypingIndicator();
            this.showTemporaryStatus(messageElement, 'Failed to regenerate response', 'error');
        }
    }

    // File Upload and GitHub Integration Methods
    setupFileUpload() {
        console.log('Setting up file upload functionality...');
        
        const addBtn = document.getElementById('addBtn');
        const addBtnMain = document.getElementById('addBtnMain'); // Main search bar add button
        const addDropdown = document.getElementById('addDropdown');
        const addDropdownMain = document.getElementById('addDropdownMain'); // Main search bar dropdown
        const fileInput = document.getElementById('fileInput');
        const imageInput = document.getElementById('imageInput');
        const githubModal = document.getElementById('githubModal');

        console.log('Elements found:', {
            addBtn: !!addBtn,
            addBtnMain: !!addBtnMain,
            addDropdown: !!addDropdown,
            addDropdownMain: !!addDropdownMain,
            fileInput: !!fileInput,
            imageInput: !!imageInput,
            githubModal: !!githubModal
        });

        // Add button click handler (main input area)
        if (addBtn && addDropdown) {
            console.log('Setting up main addBtn event listener');
            addBtn.addEventListener('click', (e) => {
                console.log('Main addBtn clicked!');
                e.preventDefault();
                e.stopPropagation();
                const isVisible = addDropdown.style.display === 'block';
                addDropdown.style.display = isVisible ? 'none' : 'block';
                
                // Position dropdown directly below the + button
                if (!isVisible) {
                    const btnRect = addBtn.getBoundingClientRect();
                    addDropdown.style.position = 'fixed';
                    addDropdown.style.top = (btnRect.bottom + 5) + 'px';
                    addDropdown.style.left = btnRect.left + 'px';
                    addDropdown.style.zIndex = '10000';
                    console.log('Dropdown positioned at:', { top: btnRect.bottom + 5, left: btnRect.left });
                }
                
                // Hide main search dropdown if open
                if (addDropdownMain) {
                    addDropdownMain.style.display = 'none';
                }
            });
        } else {
            console.warn('Main chat addBtn or addDropdown not found (normal if not on chat page)');
        }

        // Add button click handler (main search bar)
        if (addBtnMain && addDropdownMain) {
            console.log('Setting up addBtnMain event listener');
            addBtnMain.addEventListener('click', (e) => {
                console.log('addBtnMain clicked!');
                e.preventDefault();
                e.stopPropagation();
                const isVisible = addDropdownMain.style.display === 'block';
                addDropdownMain.style.display = isVisible ? 'none' : 'block';
                
                // Position dropdown directly below the + button
                if (!isVisible) {
                    const btnRect = addBtnMain.getBoundingClientRect();
                    addDropdownMain.style.position = 'fixed';
                    addDropdownMain.style.top = (btnRect.bottom + 5) + 'px';
                    addDropdownMain.style.left = btnRect.left + 'px';
                    addDropdownMain.style.zIndex = '10000';
                    console.log('Main dropdown positioned at:', { top: btnRect.bottom + 5, left: btnRect.left });
                }
                
                // Hide chat dropdown if open
                if (addDropdown) {
                    addDropdown.style.display = 'none';
                }
            });
        } else {
            console.warn('addBtnMain or addDropdownMain not found (normal if not on main search page):', {
                addBtnMain: !!addBtnMain,
                addDropdownMain: !!addDropdownMain
            });
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const isInAddBtn = addBtn && addBtn.contains(e.target);
            const isInAddBtnMain = addBtnMain && addBtnMain.contains(e.target);
            const isInDropdown = addDropdown && addDropdown.contains(e.target);
            const isInDropdownMain = addDropdownMain && addDropdownMain.contains(e.target);
            
            if (!isInAddBtn && !isInAddBtnMain && !isInDropdown && !isInDropdownMain) {
                if (addDropdown) addDropdown.style.display = 'none';
                if (addDropdownMain) addDropdownMain.style.display = 'none';
            }
        });

        // Dropdown item handlers (chat area)
        const addFileBtn = document.getElementById('addFileBtn');
        const addImageBtn = document.getElementById('addImageBtn');
        const connectGithubBtn = document.getElementById('connectGithubBtn');
        const pasteCodeBtn = document.getElementById('pasteCodeBtn');

        if (addFileBtn && fileInput && addDropdown) {
            addFileBtn.addEventListener('click', () => {
                fileInput.click();
                addDropdown.style.display = 'none';
            });
        }

        if (addImageBtn && imageInput && addDropdown) {
            addImageBtn.addEventListener('click', () => {
                imageInput.click();
                addDropdown.style.display = 'none';
            });
        }

        if (connectGithubBtn && githubModal && addDropdown) {
            connectGithubBtn.addEventListener('click', () => {
                githubModal.style.display = 'flex';
                addDropdown.style.display = 'none';
            });
        }

        if (pasteCodeBtn && addDropdown) {
            pasteCodeBtn.addEventListener('click', () => {
                this.openCodePasteDialog();
                addDropdown.style.display = 'none';
            });
        }

        // Main search dropdown item handlers
        if (addDropdownMain) {
            const addFileMainBtn = document.getElementById('addFileMainBtn');
            const addImageMainBtn = document.getElementById('addImageMainBtn');
            const connectGithubMainBtn = document.getElementById('connectGithubMainBtn');
            const pasteCodeMainBtn = document.getElementById('pasteCodeMainBtn');

            if (addFileMainBtn && fileInput) {
                addFileMainBtn.addEventListener('click', () => {
                    console.log('addFileMainBtn clicked');
                    fileInput.click();
                    addDropdownMain.style.display = 'none';
                });
            }

            if (addImageMainBtn && imageInput) {
                addImageMainBtn.addEventListener('click', () => {
                    console.log('addImageMainBtn clicked');
                    imageInput.click();
                    addDropdownMain.style.display = 'none';
                });
            }

            if (connectGithubMainBtn && githubModal) {
                connectGithubMainBtn.addEventListener('click', () => {
                    console.log('connectGithubMainBtn clicked');
                    githubModal.style.display = 'flex';
                    addDropdownMain.style.display = 'none';
                });
            }

            if (pasteCodeMainBtn) {
                pasteCodeMainBtn.addEventListener('click', () => {
                    console.log('pasteCodeMainBtn clicked');
                    this.openCodePasteDialog();
                    addDropdownMain.style.display = 'none';
                });
            }
        }

        // File input handlers
        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
        }
        
        if (imageInput) {
            imageInput.addEventListener('change', (e) => this.handleImageUpload(e));
        }

        // GitHub modal handlers
        if (githubModal) {
            this.setupGithubModal();
        }
    }

    handleFileUpload(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;

        // Validate file sizes (max 10MB per file)
        const maxSize = 10 * 1024 * 1024; // 10MB
        const oversizedFiles = files.filter(file => file.size > maxSize);

        if (oversizedFiles.length > 0) {
            this.showFileUploadStatus(`File too large: ${oversizedFiles[0].name} (${this.formatFileSize(oversizedFiles[0].size)}). Max size: 10MB`, 'error');
            setTimeout(() => this.hideFileUploadStatus(), 4000);
            return;
        }

        files.forEach((file, index) => {
            // Show upload progress
            this.showFileUploadStatus(`Reading ${file.name}...`, 'uploading');
            this.updateFileUploadProgress(10);

            const reader = new FileReader();

            reader.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 80) + 10; // 10-90%
                    this.updateFileUploadProgress(percentComplete);
                }
            };

            reader.onload = (e) => {
                this.updateFileUploadProgress(100);
                const content = e.target.result;
                const fileInfo = {
                    name: file.name,
                    size: file.size,
                    type: file.type,
                    content: content
                };

                this.addFileToChat(fileInfo);

                // Show success
                this.showFileUploadStatus(`✅ ${file.name} uploaded successfully`, 'success');
                setTimeout(() => this.hideFileUploadStatus(), 2000);
            };

            reader.onerror = () => {
                this.showFileUploadStatus(`❌ Failed to read ${file.name}`, 'error');
                setTimeout(() => this.hideFileUploadStatus(), 3000);
            };

            // Start reading based on file type
            if (file.type.startsWith('text/') || file.name.endsWith('.md') || file.name.endsWith('.txt') || file.name.endsWith('.json')) {
                reader.readAsText(file);
            } else {
                reader.readAsDataURL(file);
            }
        });

        // Clear the input
        event.target.value = '';
    }

    handleImageUpload(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;

        // Validate file sizes (max 10MB per file)
        const maxSize = 10 * 1024 * 1024; // 10MB
        const oversizedFiles = files.filter(file => file.size > maxSize);

        if (oversizedFiles.length > 0) {
            this.showFileUploadStatus(`Image too large: ${oversizedFiles[0].name} (${this.formatFileSize(oversizedFiles[0].size)}). Max size: 10MB`, 'error');
            setTimeout(() => this.hideFileUploadStatus(), 4000);
            return;
        }

        files.forEach((file, index) => {
            // Validate image types
            if (!file.type.startsWith('image/')) {
                this.showFileUploadStatus(`Invalid file type: ${file.name}. Please select an image file.`, 'error');
                setTimeout(() => this.hideFileUploadStatus(), 3000);
                return;
            }

            // Show upload progress
            this.showFileUploadStatus(`Processing ${file.name}...`, 'uploading');
            this.updateFileUploadProgress(10);

            const reader = new FileReader();

            reader.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 80) + 10; // 10-90%
                    this.updateFileUploadProgress(percentComplete);
                }
            };

            reader.onload = (e) => {
                this.updateFileUploadProgress(100);
                const imageInfo = {
                    name: file.name,
                    size: file.size,
                    type: file.type,
                    dataUrl: e.target.result
                };

                this.addImageToChat(imageInfo);

                // Show success
                this.showFileUploadStatus(`✅ ${file.name} uploaded successfully`, 'success');
                setTimeout(() => this.hideFileUploadStatus(), 2000);
            };

            reader.onerror = () => {
                this.showFileUploadStatus(`❌ Failed to read ${file.name}`, 'error');
                setTimeout(() => this.hideFileUploadStatus(), 3000);
            };

            reader.readAsDataURL(file);
        });

        // Clear the input
        event.target.value = '';
    }

    addFileToChat(fileInfo) {
        const chatTextarea = document.getElementById('chatTextarea');
        const currentText = chatTextarea.value;
        
        let fileText = `📄 **File: ${fileInfo.name}**\n`;
        
        if (fileInfo.type.startsWith('text/') || fileInfo.name.endsWith('.md') || fileInfo.name.endsWith('.txt')) {
            fileText += `\`\`\`\n${fileInfo.content}\n\`\`\`\n\n`;
        } else {
            fileText += `File type: ${fileInfo.type}, Size: ${this.formatFileSize(fileInfo.size)}\n\n`;
        }
        
        chatTextarea.value = currentText + fileText;
        this.autoResizeTextarea(chatTextarea);
        chatTextarea.focus();
    }

    addImageToChat(imageInfo) {
        const chatTextarea = document.getElementById('chatTextarea');
        const currentText = chatTextarea.value;
        
        const imageText = `🖼️ **Image: ${imageInfo.name}** (${this.formatFileSize(imageInfo.size)})\n\nPlease analyze this image and tell me what you see.\n\n`;
        
        chatTextarea.value = currentText + imageText;
        this.autoResizeTextarea(chatTextarea);
        chatTextarea.focus();
        
        // Note: In a real implementation, you'd send the image data to the backend
        console.log('Image uploaded:', imageInfo);
    }

    setupGithubModal() {
        const modal = document.getElementById('githubModal');
        const closeBtn = document.getElementById('closeGithubModal');
        const cancelBtn = document.getElementById('cancelGithub');
        const connectBtn = document.getElementById('connectGithub');

        // Close modal handlers
        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        cancelBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        // Close modal when clicking outside
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });

        // Connect GitHub repository
        connectBtn.addEventListener('click', () => {
            this.connectGithubRepository();
        });
    }

    async connectGithubRepository() {
        const urlInput = document.getElementById('githubUrl');
        const branchInput = document.getElementById('githubBranch');
        const includeReadme = document.getElementById('includeReadme').checked;
        const includeCode = document.getElementById('includeCode').checked;

        const repoUrl = urlInput.value.trim();
        if (!repoUrl) {
            alert('Please enter a repository URL');
            return;
        }

        // Parse GitHub URL
        const match = repoUrl.match(/github\.com\/([^\/]+)\/([^\/]+)/);
        if (!match) {
            alert('Please enter a valid GitHub repository URL');
            return;
        }

        const [, owner, repo] = match;
        const branch = branchInput.value.trim() || 'main';

        try {
            connectBtn.disabled = true;
            connectBtn.textContent = 'Connecting...';

            const repoInfo = await this.fetchGithubRepository(owner, repo, branch, includeReadme, includeCode);
            this.addGithubRepoToChat(repoInfo);

            // Close modal and reset form
            document.getElementById('githubModal').style.display = 'none';
            urlInput.value = '';
            branchInput.value = '';
            document.getElementById('includeReadme').checked = false;
            document.getElementById('includeCode').checked = true;

        } catch (error) {
            console.error('Error connecting to GitHub:', error);
            alert('Failed to connect to repository. Please check the URL and try again.');
        } finally {
            connectBtn.disabled = false;
            connectBtn.textContent = 'Connect Repository';
        }
    }

    async fetchGithubRepository(owner, repo, branch, includeReadme, includeCode) {
        const baseUrl = `https://api.github.com/repos/${owner}/${repo}`;
        
        // Get repository info
        const repoResponse = await fetch(baseUrl);
        if (!repoResponse.ok) {
            throw new Error('Repository not found');
        }
        const repoData = await repoResponse.json();

        const result = {
            name: repoData.name,
            fullName: repoData.full_name,
            description: repoData.description,
            language: repoData.language,
            stars: repoData.stargazers_count,
            url: repoData.html_url,
            files: []
        };

        // Get repository contents
        if (includeReadme || includeCode) {
            try {
                const contentsResponse = await fetch(`${baseUrl}/contents?ref=${branch}`);
                if (contentsResponse.ok) {
                    const contents = await contentsResponse.json();
                    
                    for (const item of contents) {
                        if (item.type === 'file') {
                            if ((includeReadme && item.name.toLowerCase().includes('readme')) ||
                                (includeCode && this.isCodeFile(item.name))) {
                                
                                try {
                                    const fileResponse = await fetch(item.download_url);
                                    if (fileResponse.ok) {
                                        const content = await fileResponse.text();
                                        result.files.push({
                                            name: item.name,
                                            path: item.path,
                                            content: content.slice(0, 5000) // Limit content length
                                        });
                                    }
                                } catch (e) {
                                    console.warn(`Failed to fetch ${item.name}:`, e);
                                }
                            }
                        }
                    }
                }
            } catch (e) {
                console.warn('Failed to fetch repository contents:', e);
            }
        }

        return result;
    }

    isCodeFile(filename) {
        const codeExtensions = ['.js', '.ts', '.py', '.java', '.cpp', '.c', '.h', '.css', '.html', '.jsx', '.tsx', '.vue', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.r', '.sql'];
        return codeExtensions.some(ext => filename.toLowerCase().endsWith(ext));
    }

    addGithubRepoToChat(repoInfo) {
        const chatTextarea = document.getElementById('chatTextarea');
        const currentText = chatTextarea.value;
        
        let repoText = `🐙 **GitHub Repository: ${repoInfo.fullName}**\n`;
        repoText += `🔗 ${repoInfo.url}\n`;
        if (repoInfo.description) {
            repoText += `📝 ${repoInfo.description}\n`;
        }
        if (repoInfo.language) {
            repoText += `💻 Primary language: ${repoInfo.language}\n`;
        }
        repoText += `⭐ ${repoInfo.stars} stars\n\n`;

        if (repoInfo.files && repoInfo.files.length > 0) {
            repoText += `**Included files:**\n`;
            repoInfo.files.forEach(file => {
                repoText += `\n📄 **${file.name}**\n`;
                repoText += `\`\`\`${this.getLanguageFromExtension(file.name)}\n`;
                repoText += `${file.content}\n`;
                repoText += `\`\`\`\n`;
            });
        }

        repoText += `\nPlease analyze this repository and help me understand its structure and functionality.\n\n`;
        
        chatTextarea.value = currentText + repoText;
        this.autoResizeTextarea(chatTextarea);
        chatTextarea.focus();
    }

    getLanguageFromExtension(filename) {
        const extensions = {
            '.js': 'javascript',
            '.ts': 'typescript',
            '.py': 'python',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.css': 'css',
            '.html': 'html',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.vue': 'vue',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.r': 'r',
            '.sql': 'sql'
        };
        
        const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'));
        return extensions[ext] || '';
    }

    openCodePasteDialog() {
        const code = prompt('Paste your code here:');
        if (code) {
            const chatTextarea = document.getElementById('chatTextarea');
            const currentText = chatTextarea.value;
            const codeText = `💻 **Code:**\n\`\`\`\n${code}\n\`\`\`\n\nPlease review and help me with this code.\n\n`;
            chatTextarea.value = currentText + codeText;
            this.autoResizeTextarea(chatTextarea);
            chatTextarea.focus();
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }

    processCodeBlocks(content) {
        // Handle multiline code blocks (```code```)
        content = content.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, language, code) => {
            const lang = language || 'text';
            const codeId = 'code_' + Math.random().toString(36).substr(2, 9);
            
            // Preserve the original code exactly - don't trim too aggressively
            let rawCode = code;
            
            // Only remove leading/trailing empty lines, preserve internal spacing
            rawCode = rawCode.replace(/^\n+/, '').replace(/\n+$/, '');
            
            // Store the completely unprocessed code for copying
            const displayCode = rawCode; // What we show in the UI
            
            return `<div class="code-block">
                <div class="code-header">
                    <span class="code-language">${lang}</span>
                    <button class="copy-btn" data-code-id="${codeId}" title="Copy code">
                        <img src="/SVGs/copy.svg" alt="Copy" class="copy-icon">
                        Copy
                    </button>
                </div>
                <pre><code id="${codeId}" class="language-${lang}" data-raw-code="${this.escapeForDataAttribute(rawCode)}">${this.escapeHtml(displayCode)}</code></pre>
            </div>`;
        });
        
        return content;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    escapeForDataAttribute(text) {
        return text
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    decodeHtmlEntities(text) {
        return text
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&amp;/g, '&')
            .replace(/&quot;/g, '"')
            .replace(/&#39;/g, "'");
    }

    // Search functionality
    initializeSearch() {
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterMessages(e.target.value);
            });
        }
    }

    initializeMobileMenu() {
        console.log('🔧 Initializing mobile menu...');
        const mobileMenuBtn = document.getElementById('mobileMenuBtn');
        const sidebar = document.getElementById('sidebar');
        const sidebarOverlay = document.getElementById('sidebarOverlay');
        
        console.log('Mobile menu elements:', { 
            button: !!mobileMenuBtn, 
            sidebar: !!sidebar, 
            overlay: !!sidebarOverlay 
        });
        
        if (mobileMenuBtn && sidebar && sidebarOverlay) {
            // Toggle sidebar on button click
            mobileMenuBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                console.log('📱 Mobile menu button clicked!');
                const isActive = sidebar.classList.contains('active');
                console.log('Current state:', isActive ? 'open' : 'closed');
                
                sidebar.classList.toggle('active');
                sidebarOverlay.classList.toggle('active');
                
                console.log('New state:', sidebar.classList.contains('active') ? 'open' : 'closed');
            });
            
            // Close sidebar when overlay is clicked
            sidebarOverlay.addEventListener('click', () => {
                console.log('📱 Overlay clicked, closing sidebar');
                sidebar.classList.remove('active');
                sidebarOverlay.classList.remove('active');
            });
            
            // Close sidebar when a conversation is selected (mobile only)
            const historyItems = sidebar.querySelectorAll('.history-item');
            historyItems.forEach(item => {
                item.addEventListener('click', () => {
                    if (window.innerWidth <= 768) {
                        console.log('📱 History item clicked on mobile, closing sidebar');
                        sidebar.classList.remove('active');
                        sidebarOverlay.classList.remove('active');
                    }
                });
            });
            
            // Close sidebar when new chat is clicked (mobile only)
            const newChatBtn = document.getElementById('newChatBtn');
            if (newChatBtn) {
                newChatBtn.addEventListener('click', () => {
                    if (window.innerWidth <= 768) {
                        console.log('📱 New chat clicked on mobile, closing sidebar');
                        sidebar.classList.remove('active');
                        sidebarOverlay.classList.remove('active');
                    }
                });
            }
            
            console.log('✅ Mobile menu initialized successfully');
        } else {
            console.error('❌ Mobile menu initialization failed - missing elements');
        }
        
        // Setup mobile tools FAB
        this.setupMobileToolsFab();
    }
    
    setupMobileToolsFab() {
        const mobileToolsFab = document.getElementById('mobileToolsFab');
        const toolsPanel = document.getElementById('toolsPanel');
        const sidebarOverlay = document.getElementById('sidebarOverlay');
        
        if (mobileToolsFab && toolsPanel) {
            // Show FAB only on mobile
            if (window.innerWidth <= 768) {
                mobileToolsFab.style.display = 'flex';
            }
            
            // Handle window resize
            window.addEventListener('resize', () => {
                if (window.innerWidth <= 768) {
                    mobileToolsFab.style.display = 'flex';
                } else {
                    mobileToolsFab.style.display = 'none';
                    toolsPanel.classList.remove('active');
                }
            });
            
            // Toggle tools panel on FAB click
            mobileToolsFab.addEventListener('click', (e) => {
                e.stopPropagation();
                const isActive = toolsPanel.classList.toggle('active');
                
                // Update FAB icon based on state
                const icon = mobileToolsFab.querySelector('span');
                if (icon) {
                    icon.textContent = isActive ? '✕' : '⚙️';
                }
                
                // Show overlay when tools panel is open
                if (sidebarOverlay) {
                    if (isActive) {
                        sidebarOverlay.classList.add('active');
                    } else {
                        sidebarOverlay.classList.remove('active');
                    }
                }
            });
            
            // Close tools panel when overlay is clicked
            if (sidebarOverlay) {
                sidebarOverlay.addEventListener('click', () => {
                    if (toolsPanel.classList.contains('active')) {
                        toolsPanel.classList.remove('active');
                        const icon = mobileToolsFab.querySelector('span');
                        if (icon) {
                            icon.textContent = '⚙️';
                        }
                    }
                });
            }
            
        }
    }
    
    // Voice Chat Integration
    initializeVoiceChat() {
        console.log('🎤 Initializing voice chat...');
        
        // Create voice chat instance
        this.voiceChat = new VoiceChat();
        
        // Setup callbacks
        this.voiceChat.onListeningStart = () => this.handleListeningStart();
        this.voiceChat.onListeningEnd = () => this.handleListeningEnd();
        this.voiceChat.onListeningError = (error) => this.handleListeningError(error);
        this.voiceChat.onTranscriptInterim = (transcript) => this.handleTranscriptInterim(transcript);
        this.voiceChat.onTranscriptFinal = (transcript) => this.handleTranscriptFinal(transcript);
        this.voiceChat.onSpeakingStart = () => this.handleSpeakingStart();
        this.voiceChat.onSpeakingEnd = () => this.handleSpeakingEnd();
        
        // Setup voice buttons
        this.setupVoiceButtons();
        
        console.log('✅ Voice chat initialized');
    }
    
    setupVoiceButtons() {
        // Main search bar voice button
        const voiceBtnMain = document.getElementById('voiceBtn');
        if (voiceBtnMain) {
            voiceBtnMain.addEventListener('click', () => this.toggleVoiceInput('search'));
        }
        
        // Chat area voice buttons
        const voiceBtnsChat = document.querySelectorAll('.input-btn.voice-btn');
        voiceBtnsChat.forEach(btn => {
            if (btn !== voiceBtnMain) {
                btn.addEventListener('click', () => this.toggleVoiceInput('chat'));
            }
        });
    }
    
    toggleVoiceInput(context) {
        if (this.voiceChat.isListening) {
            this.voiceChat.stopListening();
        } else {
            const started = this.voiceChat.startListening();
            if (!started) {
                // Show error notification
                this.showNotification('Voice input not available in your browser. Please use Chrome or Edge.', 'error');
            }
            this.currentVoiceContext = context;
        }
    }
    
    handleListeningStart() {
        console.log('🎤 Listening started');

        // Update all voice buttons to show listening state
        const voiceButtons = document.querySelectorAll('.voice-btn');
        voiceButtons.forEach(btn => {
            btn.classList.add('listening');
            btn.setAttribute('aria-label', 'Stop voice input');
        });

        // Show voice status indicator
        this.showVoiceStatus('Listening... Speak now', 'listening');
    }

    handleListeningEnd() {
        console.log('🎤 Listening ended');

        // Reset all voice buttons
        const voiceButtons = document.querySelectorAll('.voice-btn');
        voiceButtons.forEach(btn => {
            btn.classList.remove('listening');
            btn.setAttribute('aria-label', 'Start voice input');
        });

        // Hide voice status indicator
        this.hideVoiceStatus();
    }

    handleListeningError(error) {
        console.error('🎤 Listening error:', error);

        const errorMessages = {
            'no-speech': 'No speech detected. Please try again.',
            'audio-capture': 'Microphone access denied or not available.',
            'not-allowed': 'Microphone permission denied. Please allow microphone access and refresh the page.',
            'network': 'Network error. Please check your connection.',
            'service-not-allowed': 'Voice recognition service not available.',
            'aborted': 'Voice input was cancelled.',
            'language-not-supported': 'Selected language is not supported.',
            'bad-grammar': 'Speech recognition grammar error.'
        };

        const message = errorMessages[error] || `Voice input error: ${error}`;

        // Reset voice buttons
        const voiceButtons = document.querySelectorAll('.voice-btn');
        voiceButtons.forEach(btn => {
            btn.classList.remove('listening');
            btn.setAttribute('aria-label', 'Start voice input');
        });

        // Show error status
        this.showVoiceStatus(message, 'error');

        // Hide error after 5 seconds
        setTimeout(() => this.hideVoiceStatus(), 5000);
    }
    
    handleTranscriptInterim(transcript) {
        console.log('🎤 Interim:', transcript);

        // Show interim results in input field (with lighter text)
        const input = this.currentVoiceContext === 'search' ? this.chatInput : this.chatTextarea;
        if (input) {
            input.value = transcript;
            input.style.opacity = '0.6';
            input.style.fontStyle = 'italic';
        }

        // Update status indicator
        this.updateVoiceStatus(`"${transcript}"`, 'listening');
    }

    handleTranscriptFinal(transcript) {
        console.log('🎤 Final:', transcript);

        // Set final transcript in input field
        const input = this.currentVoiceContext === 'search' ? this.chatInput : this.chatTextarea;
        if (input) {
            input.value = transcript;
            input.style.opacity = '1';
            input.style.fontStyle = 'normal';

            // Focus input
            input.focus();

            // Update char count if in chat mode
            if (this.currentVoiceContext === 'chat') {
                this.updateCharCount();
            }
        }

        // Show success status
        this.showVoiceStatus('✅ Voice input captured', 'success');

        // Hide success status after 2 seconds
        setTimeout(() => this.hideVoiceStatus(), 2000);
    }
    
    handleSpeakingStart() {
        console.log('🔊 Speaking started');
        
        // Could add visual indication that AI is speaking
        const messages = document.querySelectorAll('.message.assistant');
        const lastMessage = messages[messages.length - 1];
        if (lastMessage) {
            lastMessage.classList.add('speaking');
        }
    }
    
    handleSpeakingEnd() {
        console.log('🔊 Speaking ended');
        
        // Remove speaking indication
        const messages = document.querySelectorAll('.message.speaking');
        messages.forEach(msg => msg.classList.remove('speaking'));
    }
    
    showVoiceStatus(message, type = 'info') {
        const statusElement = document.getElementById('voiceStatus');
        const statusText = document.getElementById('voiceStatusText');
        const statusIcon = statusElement.querySelector('.voice-status-icon');

        if (!statusElement || !statusText) return;

        // Update text and type
        statusText.textContent = message;
        statusElement.className = `voice-status ${type}`;

        // Update icon based on type
        const icons = {
            listening: '🎤',
            success: '✅',
            error: '❌',
            info: 'ℹ️'
        };
        statusIcon.textContent = icons[type] || icons.info;

        // Show the status
        statusElement.classList.add('show');
    }

    updateVoiceStatus(message, type = 'info') {
        const statusElement = document.getElementById('voiceStatus');
        const statusText = document.getElementById('voiceStatusText');

        if (!statusElement || !statusText || !statusElement.classList.contains('show')) return;

        statusText.textContent = message;
        statusElement.className = `voice-status ${type}`;
    }

    hideVoiceStatus() {
        const statusElement = document.getElementById('voiceStatus');
        if (statusElement) {
            statusElement.classList.remove('show');
        }
    }

    showFileUploadStatus(message, type = 'uploading') {
        const statusElement = document.getElementById('fileUploadStatus');
        const statusText = document.getElementById('fileUploadText');
        const statusIcon = statusElement.querySelector('.file-upload-icon');

        if (!statusElement || !statusText) return;

        // Update text and type
        statusText.textContent = message;
        statusElement.className = `file-upload-status ${type}`;

        // Update icon based on type
        const icons = {
            uploading: '📄',
            success: '✅',
            error: '❌'
        };
        statusIcon.textContent = icons[type] || icons.uploading;

        // Show the status
        statusElement.classList.add('show');
    }

    updateFileUploadProgress(percent) {
        const progressBar = document.getElementById('fileUploadBar');
        if (progressBar) {
            progressBar.style.width = percent + '%';
        }
    }

    hideFileUploadStatus() {
        const statusElement = document.getElementById('fileUploadStatus');
        if (statusElement) {
            statusElement.classList.remove('show');
            // Reset progress bar
            this.updateFileUploadProgress(0);
        }
    }
    
    // Add edit query button to messages
    addEditQueryButton(messageElement, queryText) {
        const actionsDiv = messageElement.querySelector('.message-actions') || document.createElement('div');
        actionsDiv.className = 'message-actions';
        
        const editBtn = document.createElement('button');
        editBtn.className = 'message-action-btn edit-btn';
        editBtn.title = 'Edit and resend';
        editBtn.innerHTML = '✏️';
        editBtn.addEventListener('click', () => {
            // Populate input with query text
            if (this.isWelcomeState) {
                this.chatInput.value = queryText;
                this.chatInput.focus();
            } else {
                this.chatTextarea.value = queryText;
                this.chatTextarea.focus();
                this.updateCharCount();
            }
            
            // Scroll to input
            const inputArea = this.isWelcomeState ? this.chatInput.parentElement : this.inputArea;
            inputArea?.scrollIntoView({ behavior: 'smooth', block: 'end' });
        });
        
        actionsDiv.appendChild(editBtn);
        
        if (!messageElement.querySelector('.message-actions')) {
            messageElement.appendChild(actionsDiv);
        }
    }
    
    showNotification(message, type = 'info', duration = 3000) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#3b82f6'};
            color: white;
            font-size: 14px;
            z-index: 10000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideIn 0.3s ease-out;
        `;
        
        document.body.appendChild(notification);
        
        // Auto remove after duration
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => notification.remove(), 300);
        }, duration);
    }

    // Edit query message - populate input with query text for editing
    editQueryMessage(messageId, content) {
        console.log('📝 Edit query:', messageId, content);
        
        try {
            // Find the message element and delete it along with the response
            const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
            if (messageElement) {
                // Find and remove the assistant's response that follows
                let nextElement = messageElement.nextElementSibling;
                while (nextElement && !nextElement.classList.contains('message-group')) {
                    const toRemove = nextElement;
                    nextElement = nextElement.nextElementSibling;
                    if (toRemove.classList.contains('message-group') && toRemove.querySelector('.companion-logo')) {
                        toRemove.remove();
                        break;
                    }
                }
                
                // Remove the user's message
                messageElement.remove();
            }
            
            // Determine which input to use based on current state
            let targetInput = null;
            
            if (this.isWelcomeState && this.chatInput) {
                targetInput = this.chatInput;
            } else if (this.chatTextarea) {
                targetInput = this.chatTextarea;
            }
            
            if (!targetInput) {
                console.error('No input element found');
                this.showNotification('Error: Input field not found', 'error');
                return;
            }
            
            // Populate the input with the query
            targetInput.value = content;
            
            // Update character count if available
            if (this.chatTextarea === targetInput && this.updateCharCount) {
                this.updateCharCount();
            }
            
            // Focus the input and scroll into view
            targetInput.focus();
            targetInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Show success notification
            this.showNotification('Editing query - modify and send', 'info', 2000);
            
        } catch (error) {
            console.error('Error editing query:', error);
            this.showNotification('Error editing query', 'error');
        }
    }

    // Fix main search bar dropdown
    fixMainSearchDropdown() {
        const addBtnMain = document.getElementById('addBtnMain');
        const addDropdownMain = document.getElementById('addDropdownMain');
        
        if (addBtnMain && addDropdownMain) {
            console.log('✅ Main search dropdown elements found');
            
            // Make sure dropdown is properly styled and positioned
            addDropdownMain.style.position = 'absolute';
            addDropdownMain.style.display = 'none';
            
            // Click handler
            addBtnMain.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('Main search + button clicked');
                
                const isVisible = addDropdownMain.style.display === 'block';
                addDropdownMain.style.display = isVisible ? 'none' : 'block';
                
                // Position the dropdown directly below the + button
                const btnRect = addBtnMain.getBoundingClientRect();
                addDropdownMain.style.top = (btnRect.bottom + 5) + 'px';
                addDropdownMain.style.left = btnRect.left + 'px';
            });
            
            // Main dropdown item handlers
            const addFileMainBtn = document.getElementById('addFileMainBtn');
            const addImageMainBtn = document.getElementById('addImageMainBtn');
            const connectGithubMainBtn = document.getElementById('connectGithubMainBtn');
            const pasteCodeMainBtn = document.getElementById('pasteCodeMainBtn');
            const fileInput = document.getElementById('fileInput');
            const imageInput = document.getElementById('imageInput');
            const githubModal = document.getElementById('githubModal');
            
            if (addFileMainBtn && fileInput) {
                addFileMainBtn.addEventListener('click', () => {
                    fileInput.click();
                    addDropdownMain.style.display = 'none';
                });
            }
            
            if (addImageMainBtn && imageInput) {
                addImageMainBtn.addEventListener('click', () => {
                    imageInput.click();
                    addDropdownMain.style.display = 'none';
                });
            }
            
            if (connectGithubMainBtn && githubModal) {
                connectGithubMainBtn.addEventListener('click', () => {
                    githubModal.style.display = 'flex';
                    addDropdownMain.style.display = 'none';
                });
            }
            
            if (pasteCodeMainBtn) {
                pasteCodeMainBtn.addEventListener('click', () => {
                    this.openCodePasteDialog();
                    addDropdownMain.style.display = 'none';
                });
            }
            
            console.log('✅ Main search dropdown handlers attached');
        } else {
            console.error('❌ Main search dropdown elements not found:', {
                addBtnMain: !!addBtnMain,
                addDropdownMain: !!addDropdownMain
            });
        }
    }
    
    openCodePasteDialog() {
        // Create a simple code paste modal
        const modal = document.createElement('div');
        modal.className = 'code-paste-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
        `;
        
        const content = document.createElement('div');
        content.style.cssText = `
            background: #1a1a1a;
            border-radius: 12px;
            padding: 24px;
            max-width: 600px;
            width: 90%;
            max-height: 70vh;
            display: flex;
            flex-direction: column;
        `;
        
        content.innerHTML = `
            <h3 style="color: white; margin: 0 0 16px 0;">Paste Your Code</h3>
            <textarea 
                id="codePasteArea" 
                placeholder="Paste your code here..."
                style="
                    flex: 1;
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 8px;
                    padding: 12px;
                    color: white;
                    font-family: 'Courier New', monospace;
                    font-size: 14px;
                    resize: none;
                    margin-bottom: 16px;
                "
            ></textarea>
            <div style="display: flex; gap: 8px; justify-content: flex-end;">
                <button id="cancelCodePaste" style="
                    padding: 8px 16px;
                    border: none;
                    border-radius: 6px;
                    background: #333;
                    color: white;
                    cursor: pointer;
                ">Cancel</button>
                <button id="insertCode" style="
                    padding: 8px 16px;
                    border: none;
                    border-radius: 6px;
                    background: #3b82f6;
                    color: white;
                    cursor: pointer;
                ">Insert Code</button>
            </div>
        `;
        
        modal.appendChild(content);
        document.body.appendChild(modal);
        
        const textarea = document.getElementById('codePasteArea');
        textarea.focus();
        
        // Cancel button
        document.getElementById('cancelCodePaste').addEventListener('click', () => {
            modal.remove();
        });
        
        // Insert button
        document.getElementById('insertCode').addEventListener('click', () => {
            const code = textarea.value.trim();
            if (code) {
                const codeMessage = `\`\`\`\n${code}\n\`\`\`\n\nPlease help me with this code.`;
                if (this.isWelcomeState && this.chatInput) {
                    this.chatInput.value = codeMessage;
                } else if (this.chatTextarea) {
                    this.chatTextarea.value = codeMessage;
                    this.updateCharCount();
                }
            }
            modal.remove();
        });
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    filterMessages(searchTerm) {
        const messages = document.querySelectorAll('.message');
        messages.forEach(message => {
            const messageText = message.textContent.toLowerCase();
            const shouldShow = !searchTerm || messageText.includes(searchTerm.toLowerCase());
            message.style.display = shouldShow ? 'block' : 'none';
        });
    }

    async copyCodeToClipboard(elementId, button) {
        const element = document.getElementById(elementId);
        if (element) {
            // Try to get the raw code from the data attribute first
            let text = element.getAttribute('data-raw-code') || element.getAttribute('data-original-code');
            
            if (text) {
                // Decode HTML entities properly and completely
                text = text
                    .replace(/&amp;/g, '&')  // Do & first to avoid double decoding
                    .replace(/&lt;/g, '<')
                    .replace(/&gt;/g, '>')
                    .replace(/&quot;/g, '"')
                    .replace(/&#39;/g, "'")
                    .replace(/&#x27;/g, "'")
                    .replace(/&#x2F;/g, '/');
            } else {
                // Fallback to text content if no data attribute
                text = element.textContent || element.innerText || '';
            }
            
            // Normalize line endings to Unix style (\n)
            text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
            
            // Debug logging to see what we're actually copying
            console.log('Copying text:', JSON.stringify(text.substring(0, 200)));
            
            try {
                await navigator.clipboard.writeText(text);
                
                // Visual feedback
                const originalHTML = button.innerHTML;
                button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 6L9 17l-5-5"></path>
                </svg> Copied!`;
                button.classList.add('copied');
                
                setTimeout(() => {
                    button.innerHTML = originalHTML;
                    button.classList.remove('copied');
                }, 2000);
            } catch (err) {
                console.error('Failed to copy text: ', err);
                // Enhanced fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                
                try {
                    document.execCommand('copy');
                    console.log('Fallback copy successful');
                } catch (fallbackErr) {
                    console.error('Fallback copy failed:', fallbackErr);
                }
                
                document.body.removeChild(textArea);
                
                const originalHTML = button.innerHTML;
                button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 6L9 17l-5-5"></path>
                </svg> Copied!`;
                setTimeout(() => {
                    button.innerHTML = originalHTML;
                }, 2000);
            }
        }
    }
}

// Standalone mobile menu initialization (runs immediately)
function initStandaloneMobileMenu() {
    console.log('🔧 Standalone mobile menu initializing...');
    
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    
    console.log('Elements found:', {
        button: !!mobileMenuBtn,
        sidebar: !!sidebar,
        overlay: !!sidebarOverlay
    });
    
    if (mobileMenuBtn && sidebar && sidebarOverlay) {
        console.log('✅ All elements found, attaching click handler');
        
        // Remove any existing listeners
        const newBtn = mobileMenuBtn.cloneNode(true);
        mobileMenuBtn.parentNode.replaceChild(newBtn, mobileMenuBtn);
        
        newBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('🎯 MOBILE MENU CLICKED!');
            
            const isOpen = sidebar.classList.contains('active');
            console.log('Sidebar currently:', isOpen ? 'OPEN' : 'CLOSED');
            
            if (isOpen) {
                sidebar.classList.remove('active');
                sidebarOverlay.classList.remove('active');
                console.log('➡️ Closing sidebar');
            } else {
                sidebar.classList.add('active');
                sidebarOverlay.classList.add('active');
                console.log('⬅️ Opening sidebar');
            }
        });
        
        // Close on overlay click
        sidebarOverlay.addEventListener('click', function() {
            console.log('🎯 Overlay clicked, closing sidebar');
            sidebar.classList.remove('active');
            sidebarOverlay.classList.remove('active');
        });
        
        console.log('✅ Standalone mobile menu initialized');
    } else {
        console.error('❌ Missing elements for mobile menu');
    }
}

// Run immediately when script loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStandaloneMobileMenu);
} else {
    initStandaloneMobileMenu();
}

// Initialize the chat interface when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.chatInterface = new ModernChatInterface();
});