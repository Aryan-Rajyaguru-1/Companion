// Demo Script for DeepCompanion Testing Page
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const modelTabs = document.querySelectorAll('.model-tab');
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const chatDisplay = document.getElementById('chatDisplay');
    const clearButton = document.getElementById('clearChat');
    const charCounter = document.getElementById('charCounter');
    const statusText = document.querySelector('.status-text');

    // State
    let currentModel = 'chat';
    let isTyping = false;
    let messageCount = 0;

    // Demo responses for different models
    const demoResponses = {
        chat: [
            "Hello! I'm DeepCompanion's chat AI. I'm designed for natural conversations and can help with a wide variety of topics. What would you like to discuss?",
            "That's an interesting question! In the full version, I would provide detailed, contextual responses based on advanced language models.",
            "I appreciate your curiosity! The desktop application connects to powerful AI models that can engage in much more sophisticated conversations.",
            "Great point! The real DeepCompanion can maintain context across long conversations and provide personalized assistance.",
            "I'd love to help with that! The full application has access to real-time information and advanced reasoning capabilities."
        ],
        think: [
            "🤔 **Thinking Mode Activated**\n\nLet me break this down systematically:\n\n1. **Problem Analysis**: I need to understand the core question\n2. **Information Gathering**: What facts are relevant?\n3. **Reasoning Process**: How do the pieces connect?\n4. **Conclusion**: What's the most logical answer?\n\nIn the full app, I would provide deep analytical thinking with step-by-step reasoning.",
            "🧠 **Deep Analysis Mode**\n\nThis requires careful consideration of multiple factors:\n\n• **Context**: What's the broader situation?\n• **Implications**: What are the consequences?\n• **Alternatives**: What other approaches exist?\n\nThe desktop version provides comprehensive analytical capabilities.",
            "💭 **Reasoning Framework**\n\nLet me approach this methodically:\n\n**Step 1**: Define the problem clearly\n**Step 2**: Identify key variables\n**Step 3**: Evaluate different perspectives\n**Step 4**: Synthesize insights\n\nReal DeepCompanion offers advanced logical reasoning and problem-solving.",
            "🔍 **Critical Thinking Process**\n\nThis question deserves thorough analysis:\n\n→ **Assumptions**: What premises are we working with?\n→ **Evidence**: What data supports different views?\n→ **Logic**: How do we connect the dots?\n→ **Validation**: How can we verify our conclusions?\n\nThe full application provides sophisticated analytical tools."
        ],
        code: [
            "💻 **Code Assistant Mode**\n\n```python\n# Example function (demo)\ndef solve_problem():\n    \"\"\"In the real app, I provide:\n    - Complete code solutions\n    - Debugging assistance\n    - Code explanations\n    - Best practices\n    \"\"\"\n    return \"Download the app for real coding help!\"\n```\n\nThe desktop version offers full programming assistance across all languages!",
            "🔧 **Programming Helper**\n\nI can help with:\n\n✅ **Code Generation**: Complete functions and classes\n✅ **Debugging**: Find and fix errors\n✅ **Optimization**: Improve performance\n✅ **Documentation**: Add clear comments\n✅ **Best Practices**: Follow coding standards\n\n```javascript\n// Demo - Real app provides full solutions\nfunction demonstrateCapabilities() {\n    console.log('Download for real coding assistance!');\n}\n```",
            "⚡ **Development Support**\n\nReal DeepCompanion provides:\n\n🎯 **Multi-language support**: Python, JS, Java, C++, and more\n🎯 **Framework expertise**: React, Django, Express, etc.\n🎯 **Database queries**: SQL, NoSQL optimization\n🎯 **API development**: REST, GraphQL design\n🎯 **Testing**: Unit tests and debugging\n\n```bash\n# Example - Full app gives complete solutions\ngit clone your-amazing-project\ncd your-amazing-project\npip install -r requirements.txt\n```",
            "🚀 **Code Architecture**\n\nFor complex projects, I help with:\n\n📊 **System Design**: Scalable architectures\n📊 **Code Reviews**: Quality improvements\n📊 **Performance**: Optimization strategies\n📊 **Security**: Best practices\n📊 **Documentation**: Clear explanations\n\nThe desktop app provides comprehensive development support!"
        ],
        advanced: [
            "🧠 **Advanced AI Mode Engaged**\n\nI'm operating in sophisticated reasoning mode, combining:\n\n🔬 **Multi-disciplinary Analysis**: Drawing from various fields\n🔬 **Complex Problem Solving**: Breaking down intricate challenges\n🔬 **Strategic Thinking**: Long-term implications and planning\n🔬 **Creative Solutions**: Innovative approaches\n\nThe full DeepCompanion leverages state-of-the-art models for advanced reasoning.",
            "⚛️ **Deep Reasoning Protocol**\n\nProcessing your query through advanced cognitive frameworks:\n\n→ **Semantic Understanding**: Contextual meaning analysis\n→ **Causal Reasoning**: Understanding relationships\n→ **Probabilistic Thinking**: Weighing uncertainties\n→ **Meta-cognitive Analysis**: Thinking about thinking\n\nReal DeepCompanion provides PhD-level analytical capabilities.",
            "🔮 **Advanced Intelligence Suite**\n\nActivating enhanced reasoning modules:\n\n🎭 **Philosophical Reasoning**: Deep conceptual analysis\n🎭 **Scientific Method**: Hypothesis-driven thinking\n🎭 **Systems Thinking**: Holistic perspective\n🎭 **Ethical Considerations**: Moral reasoning\n\nThe desktop version offers university-level intellectual discourse.",
            "🌟 **Maximum Capability Mode**\n\nDeploying full analytical power:\n\n⚡ **Cross-domain Integration**: Connecting diverse knowledge\n⚡ **Abstract Reasoning**: Working with complex concepts\n⚡ **Creative Problem-solving**: Novel solution generation\n⚡ **Strategic Planning**: Long-term thinking\n\nDownload DeepCompanion for genuinely advanced AI assistance!"
        ]
    };

    // Model switching
    modelTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if (isTyping) return;
            
            // Update active tab
            modelTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Update current model
            currentModel = tab.dataset.model;
            
            // Update status
            const modelNames = {
                chat: 'Chat Model',
                think: 'Think Model',
                code: 'Code Model',
                advanced: 'Advanced Model'
            };
            statusText.textContent = `Demo Mode - ${modelNames[currentModel]} Active`;
            
            // Add a system message about the switch
            addMessage('system', `🔄 Switched to ${modelNames[currentModel]}`, true);
        });
    });

    // Character counter
    messageInput.addEventListener('input', () => {
        const length = messageInput.value.length;
        charCounter.textContent = `${length} characters`;
        
        // Auto-resize textarea
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
    });

    // Send message on Enter (but allow Shift+Enter for newlines)
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Send button click
    sendButton.addEventListener('click', sendMessage);

    // Clear chat
    clearButton.addEventListener('click', () => {
        if (isTyping) return;
        
        // Keep only the welcome message
        const welcomeMessage = chatDisplay.querySelector('.welcome-message');
        chatDisplay.innerHTML = '';
        if (welcomeMessage) {
            chatDisplay.appendChild(welcomeMessage);
        }
        messageCount = 0;
        addMessage('system', '🗑️ Chat cleared', true);
    });

    // Send message function
    function sendMessage() {
        if (isTyping) return;
        
        const message = messageInput.value.trim();
        if (!message) return;

        // Add user message
        addMessage('user', message);
        
        // Clear input
        messageInput.value = '';
        messageInput.style.height = 'auto';
        charCounter.textContent = '0 characters';
        
        // Simulate AI response
        simulateAIResponse();
    }

    // Add message to chat
    function addMessage(sender, content, isSystem = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        if (isSystem) {
            messageDiv.innerHTML = `
                <div class="message-header">
                    <span class="message-avatar">⚙️</span>
                    <span class="message-sender">System</span>
                    <span class="message-time">${getCurrentTime()}</span>
                </div>
                <div class="message-content">
                    <p>${content}</p>
                </div>
            `;
        } else if (sender === 'user') {
            messageDiv.innerHTML = `
                <div class="message-header">
                    <span class="message-avatar">👤</span>
                    <span class="message-sender">You</span>
                    <span class="message-time">${getCurrentTime()}</span>
                </div>
                <div class="message-content">
                    <p>${escapeHtml(content)}</p>
                </div>
            `;
        } else {
            const modelNames = {
                chat: 'DeepCompanion Chat',
                think: 'DeepCompanion Think',
                code: 'DeepCompanion Code',
                advanced: 'DeepCompanion Advanced'
            };
            
            messageDiv.innerHTML = `
                <div class="message-header">
                    <span class="message-avatar">🤖</span>
                    <span class="message-sender">${modelNames[currentModel]}</span>
                    <span class="message-time">${getCurrentTime()}</span>
                </div>
                <div class="message-content">
                    ${formatContent(content)}
                </div>
            `;
        }
        
        chatDisplay.appendChild(messageDiv);
        chatDisplay.scrollTop = chatDisplay.scrollHeight;
        messageCount++;
    }

    // Simulate AI response with typing indicator
    function simulateAIResponse() {
        isTyping = true;
        sendButton.disabled = true;
        
        // Add typing indicator
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.innerHTML = `
            <span class="message-avatar">🤖</span>
            <span>DeepCompanion is thinking</span>
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        chatDisplay.appendChild(typingDiv);
        chatDisplay.scrollTop = chatDisplay.scrollHeight;
        
        // Simulate thinking time
        const thinkingTime = Math.random() * 2000 + 1000; // 1-3 seconds
        
        setTimeout(() => {
            // Remove typing indicator
            chatDisplay.removeChild(typingDiv);
            
            // Get appropriate response
            const responses = demoResponses[currentModel];
            const responseIndex = messageCount % responses.length;
            const response = responses[responseIndex];
            
            // Add AI response
            addMessage('assistant', response);
            
            isTyping = false;
            sendButton.disabled = false;
            messageInput.focus();
        }, thinkingTime);
    }

    // Helper functions
    function getCurrentTime() {
        return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatContent(content) {
        // Convert markdown-like formatting to HTML
        let formatted = escapeHtml(content);
        
        // Bold text
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Code blocks
        formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)\n```/g, (match, lang, code) => {
            return `<pre><code class="language-${lang || 'text'}">${code}</code></pre>`;
        });
        
        // Inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Lists
        formatted = formatted.replace(/^(→|✅|🎯|📊|⚡|🎭) (.*$)/gm, '<li>$1 $2</li>');
        
        // Wrap lists
        formatted = formatted.replace(/(<li>.*<\/li>\s*)+/gs, '<ul>$&</ul>');
        
        // Line breaks
        formatted = formatted.replace(/\n\n/g, '</p><p>');
        formatted = formatted.replace(/\n/g, '<br>');
        
        // Wrap in paragraphs if not already wrapped
        if (!formatted.includes('<p>') && !formatted.includes('<ul>') && !formatted.includes('<pre>')) {
            formatted = `<p>${formatted}</p>`;
        }
        
        return formatted;
    }

    // Demo tips
    const demoTips = [
        "💡 Try switching between different AI models to see how they respond differently!",
        "🎯 Ask about coding, philosophy, science, or just have a casual conversation!",
        "⚡ The real app provides much more sophisticated and accurate responses!",
        "🚀 Download DeepCompanion to experience the full power of local and cloud AI models!"
    ];

    // Show random tips periodically
    function showRandomTip() {
        if (isTyping || messageCount < 3) return;
        
        const tip = demoTips[Math.floor(Math.random() * demoTips.length)];
        setTimeout(() => {
            if (!isTyping) {
                addMessage('system', tip, true);
            }
        }, Math.random() * 3000 + 2000);
    }

    // Show tips every few interactions
    setInterval(() => {
        if (Math.random() < 0.3) { // 30% chance
            showRandomTip();
        }
    }, 30000); // Every 30 seconds

    // Focus input on load
    messageInput.focus();

    // Demo welcome message after a short delay
    setTimeout(() => {
        addMessage('system', '🚀 Welcome to the DeepCompanion demo! Try asking a question or switching AI models.', true);
    }, 2000);
});
