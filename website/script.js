// Companion Demo Interface JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const demoInput = document.getElementById('demoInput');
    const demoSend = document.getElementById('demoSend');
    const demoMessages = document.getElementById('demoMessages');
    const exampleButtons = document.querySelectorAll('.example-btn');
    
    // Backend API configuration
    const API_BASE = 'http://localhost:8001';
    let isBackendConnected = false;
    
    // Check backend connection on load
    checkBackendConnection();
    
    // Handle demo input
    if (demoInput && demoSend) {
        demoSend.addEventListener('click', sendMessage);
        demoInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }
    
    // Handle example buttons
    exampleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const text = this.getAttribute('data-text');
            if (text) {
                demoInput.value = text;
                sendMessage();
            }
        });
    });
    
    // Check if backend is running
    async function checkBackendConnection() {
        try {
            const response = await fetch(`${API_BASE}/health`);
            if (response.ok) {
                isBackendConnected = true;
                updateConnectionStatus(true);
            } else {
                isBackendConnected = false;
                updateConnectionStatus(false);
            }
        } catch (error) {
            isBackendConnected = false;
            updateConnectionStatus(false);
        }
    }
    
    // Update connection status display
    function updateConnectionStatus(connected) {
        const statusElement = document.querySelector('.demo-status');
        const indicator = document.querySelector('.status-indicator');
        
        if (statusElement && indicator) {
            if (connected) {
                statusElement.innerHTML = '<span class="status-indicator connected"></span>Connected to Backend';
                statusElement.style.color = '#10b981';
            } else {
                statusElement.innerHTML = '<span class="status-indicator disconnected"></span>Demo Mode (No Backend)';
                statusElement.style.color = '#f59e0b';
            }
        }
    }
    
    // Send message function
    async function sendMessage() {
        const message = demoInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        addMessage('user', message);
        demoInput.value = '';
        
        // Show thinking state
        const thinkingId = addMessage('assistant', 'Thinking...', true);
        
        try {
            let response;
            if (isBackendConnected) {
                // Try real API call
                response = await callBackendAPI(message);
            } else {
                // Fall back to demo responses
                response = getDemoResponse(message);
            }
            
            // Remove thinking message and add response
            removeMessage(thinkingId);
            addMessage('assistant', response);
            
        } catch (error) {
            removeMessage(thinkingId);
            addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
            console.error('Error:', error);
        }
    }
    
    // Call backend API
    async function callBackendAPI(message) {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                model: 'deepseek-r1:1.5b' // Default model
            })
        });
        
        if (!response.ok) {
            throw new Error('Backend API call failed');
        }
        
        const data = await response.json();
        return data.response || 'No response received';
    }
    
    // Demo responses for when backend is not available
    function getDemoResponse(message) {
        const lowerMessage = message.toLowerCase();
        
        if (lowerMessage.includes('quantum')) {
            return 'Quantum computing is like having a computer that can be in multiple states at once, similar to how a coin can be both heads and tails while spinning. This allows quantum computers to solve certain problems exponentially faster than classical computers.';
        } else if (lowerMessage.includes('python') && lowerMessage.includes('sort')) {
            return '```python\\ndef sort_list(items):\\n    return sorted(items)\\n\\n# Example usage:\\nmy_list = [3, 1, 4, 1, 5, 9, 2, 6]\\nsorted_list = sort_list(my_list)\\nprint(sorted_list)  # [1, 1, 2, 3, 4, 5, 6, 9]\\n```';
        } else if (lowerMessage.includes('renewable energy')) {
            return 'Renewable energy offers many benefits: 🌱 Environmental protection by reducing carbon emissions, 💰 Long-term cost savings, ⚡ Energy independence, 🔄 Sustainable and inexhaustible sources, and 💼 Job creation in green industries.';
        } else if (lowerMessage.includes('hello') || lowerMessage.includes('hi')) {
            return 'Hello! I\'m Companion v3.0. I can help you with questions about technology, coding, science, and more. What would you like to know?';
        } else {
            return `I understand you're asking about "${message}". This is a demo interface - for full AI capabilities, please download the desktop application or ensure the backend server is running!`;
        }
    }
    
    // Add message to chat
    function addMessage(sender, content, isTemporary = false) {
        const messageId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        const messageDiv = document.createElement('div');
        messageDiv.className = `demo-message ${sender}`;
        messageDiv.id = messageId;
        
        if (sender === 'user') {
            messageDiv.innerHTML = `
                <div class="message-avatar">👤</div>
                <div class="message-content">
                    <strong>You:</strong> ${content}
                </div>
            `;
        } else {
            messageDiv.innerHTML = `
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <strong>Companion:</strong> ${content}
                </div>
            `;
        }
        
        demoMessages.appendChild(messageDiv);
        demoMessages.scrollTop = demoMessages.scrollHeight;
        
        return messageId;
    }
    
    // Remove message from chat
    function removeMessage(messageId) {
        const messageElement = document.getElementById(messageId);
        if (messageElement) {
            messageElement.remove();
        }
    }
    
    // Handle navigation menu toggle
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');
    
    if (hamburger && navMenu) {
        hamburger.addEventListener('click', function() {
            navMenu.classList.toggle('active');
            hamburger.classList.toggle('active');
        });
    }
    
    // Smooth scrolling for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Demo tab switching
    const demoTabs = document.querySelectorAll('.demo-tab');
    demoTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // Remove active class from all tabs
            demoTabs.forEach(t => t.classList.remove('active'));
            // Add active class to clicked tab
            this.classList.add('active');
            
            // You could add different chat modes here
            const tabText = this.textContent.trim();
            if (tabText.includes('Think')) {
                addMessage('assistant', 'Thinking mode activated! I\'ll provide more detailed reasoning.');
            } else if (tabText.includes('Code')) {
                addMessage('assistant', 'Code mode activated! Ask me about programming.');
            } else if (tabText.includes('Chat')) {
                addMessage('assistant', 'Chat mode activated! Let\'s have a conversation.');
            }
        });
    });
    
    // Smart Download functionality
    function initializeDownloadButtons() {
        const downloadButtons = document.querySelectorAll('.download-btn');
        
        // Detect user's operating system
        function detectOS() {
            const userAgent = window.navigator.userAgent;
            const platform = window.navigator.platform;
            const macosPlatforms = ['Macintosh', 'MacIntel', 'MacPPC', 'Mac68K'];
            const windowsPlatforms = ['Win32', 'Win64', 'Windows', 'WinCE'];
            const iosPlatforms = ['iPhone', 'iPad', 'iPod'];
            
            if (macosPlatforms.indexOf(platform) !== -1) {
                return 'macOS';
            } else if (iosPlatforms.indexOf(platform) !== -1) {
                return 'iOS';
            } else if (windowsPlatforms.indexOf(platform) !== -1) {
                return 'Windows';
            } else if (/Android/.test(userAgent)) {
                return 'Android';
            } else if (/Linux/.test(platform)) {
                return 'Linux';
            }
            
            return 'Unknown';
        }
        
        // Download URLs (you can update these with actual download links)
        const downloadUrls = {
            Windows: 'https://github.com/Aryan-Rajyaguru-1/companion/releases/latest/download/companion-windows.exe',
            macOS: 'https://github.com/Aryan-Rajyaguru-1/companion/releases/latest/download/companion-macos.dmg',
            Linux: 'https://github.com/Aryan-Rajyaguru-1/companion/releases/latest/download/companion-linux.deb',
            source: 'https://github.com/Aryan-Rajyaguru-1/companion'
        };
        
        // Add click handlers to download buttons
        downloadButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                const buttonIcon = this.querySelector('i');
                let downloadType = 'source';
                
                // Determine download type based on button icon
                if (buttonIcon.classList.contains('fa-windows')) {
                    downloadType = 'Windows';
                } else if (buttonIcon.classList.contains('fa-apple')) {
                    downloadType = 'macOS';
                } else if (buttonIcon.classList.contains('fa-linux')) {
                    downloadType = 'Linux';
                }
                
                // Show download modal/confirmation
                showDownloadModal(downloadType);
            });
        });
        
        // Highlight the user's OS button
        const userOS = detectOS();
        downloadButtons.forEach(button => {
            const buttonIcon = button.querySelector('i');
            if (
                (userOS === 'Windows' && buttonIcon.classList.contains('fa-windows')) ||
                (userOS === 'macOS' && buttonIcon.classList.contains('fa-apple')) ||
                (userOS === 'Linux' && buttonIcon.classList.contains('fa-linux'))
            ) {
                button.classList.add('recommended');
                const titleSpan = button.querySelector('.btn-title');
                if (titleSpan) {
                    titleSpan.innerHTML += ' <span style="color: #27ae60;">• Recommended</span>';
                }
            }
        });
    }

    // Show download modal with instructions
    function showDownloadModal(downloadType) {
        // Create modal overlay
        const modalOverlay = document.createElement('div');
        modalOverlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(5px);
        `;
        
        // Create modal content
        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
            background: var(--surface-color);
            border-radius: 15px;
            padding: 40px;
            max-width: 500px;
            width: 90%;
            text-align: center;
            border: 1px solid var(--border-color);
        `;
        
        let iconClass = 'fas fa-download';
        let platformName = downloadType;
        let instructions = '';
        
        if (downloadType === 'Windows') {
            iconClass = 'fab fa-windows';
            instructions = `
                <p style="margin-bottom: 20px; color: var(--text-secondary);">Ready to download Companion for Windows</p>
                <div style="background: var(--background-color); padding: 20px; border-radius: 10px; margin: 20px 0; text-align: left;">
                    <h4 style="color: var(--primary-color); margin-bottom: 15px;">Installation Steps:</h4>
                    <ol style="color: var(--text-secondary); line-height: 1.8;">
                        <li>Download the installer (.exe file)</li>
                        <li>Run the installer as administrator</li>
                        <li>Follow the installation wizard</li>
                        <li>Install Ollama from <a href="https://ollama.ai" target="_blank" style="color: var(--primary-color);">ollama.ai</a></li>
                        <li>Launch Companion and enjoy!</li>
                    </ol>
                </div>
            `;
        } else if (downloadType === 'macOS') {
            iconClass = 'fab fa-apple';
            instructions = `
                <p style="margin-bottom: 20px; color: var(--text-secondary);">Ready to download Companion for macOS</p>
                <div style="background: var(--background-color); padding: 20px; border-radius: 10px; margin: 20px 0; text-align: left;">
                    <h4 style="color: var(--primary-color); margin-bottom: 15px;">Installation Steps:</h4>
                    <ol style="color: var(--text-secondary); line-height: 1.8;">
                        <li>Download the .dmg file</li>
                        <li>Open the .dmg file</li>
                        <li>Drag Companion to Applications folder</li>
                        <li>Install Ollama from <a href="https://ollama.ai" target="_blank" style="color: var(--primary-color);">ollama.ai</a></li>
                        <li>Launch Companion from Applications</li>
                    </ol>
                </div>
            `;
        } else if (downloadType === 'Linux') {
            iconClass = 'fab fa-linux';
            instructions = `
                <p style="margin-bottom: 20px; color: var(--text-secondary);">Ready to download Companion for Linux</p>
                <div style="background: var(--background-color); padding: 20px; border-radius: 10px; margin: 20px 0; text-align: left;">
                    <h4 style="color: var(--primary-color); margin-bottom: 15px;">Installation Steps:</h4>
                    <ol style="color: var(--text-secondary); line-height: 1.8;">
                        <li>Download the .deb package</li>
                        <li>Run: <code style="background: var(--surface-color); padding: 2px 6px; border-radius: 4px;">sudo dpkg -i companion-linux.deb</code></li>
                        <li>Or use: <code style="background: var(--surface-color); padding: 2px 6px; border-radius: 4px;">sudo apt install ./companion-linux.deb</code></li>
                        <li>Install Ollama: <code style="background: var(--surface-color); padding: 2px 6px; border-radius: 4px;">curl -fsSL https://ollama.ai/install.sh | sh</code></li>
                        <li>Launch Companion from terminal or app menu</li>
                    </ol>
                </div>
            `;
        }
        
        modalContent.innerHTML = `
            <i class="${iconClass}" style="font-size: 3rem; color: var(--primary-color); margin-bottom: 20px;"></i>
            <h2 style="margin-bottom: 20px;">Download Companion for ${platformName}</h2>
            ${instructions}
            <div style="display: flex; gap: 15px; justify-content: center; margin-top: 30px;">
                <button id="startDownload" style="
                    background: var(--gradient-primary);
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    font-size: 1rem;
                ">
                    <i class="fas fa-download"></i> Start Download
                </button>
                <button id="viewSource" style="
                    background: transparent;
                    color: var(--primary-color);
                    border: 2px solid var(--primary-color);
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    font-size: 1rem;
                ">
                    <i class="fab fa-github"></i> View Source
                </button>
                <button id="closeModal" style="
                    background: var(--surface-color);
                    color: var(--text-secondary);
                    border: 1px solid var(--border-color);
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    font-size: 1rem;
                ">
                    Cancel
                </button>
            </div>
            <p style="margin-top: 20px; color: var(--text-muted); font-size: 0.9rem;">
                💡 Contact: <a href="mailto:aryanrajyaguru2007@gmail.com" style="color: var(--primary-color);">aryanrajyaguru2007@gmail.com</a> | 
                📱 +91 76002 30560
            </p>
        `;
        
        modalOverlay.appendChild(modalContent);
        document.body.appendChild(modalOverlay);
        
        // Add event listeners
        document.getElementById('startDownload').addEventListener('click', function() {
            // Since we don't have actual release files yet, redirect to GitHub for now
            window.open('https://github.com/Aryan-Rajyaguru-1/companion', '_blank');
            document.body.removeChild(modalOverlay);
        });
        
        document.getElementById('viewSource').addEventListener('click', function() {
            window.open('https://github.com/Aryan-Rajyaguru-1/companion', '_blank');
            document.body.removeChild(modalOverlay);
        });
        
        document.getElementById('closeModal').addEventListener('click', function() {
            document.body.removeChild(modalOverlay);
        });
        
        // Close modal when clicking overlay
        modalOverlay.addEventListener('click', function(e) {
            if (e.target === modalOverlay) {
                document.body.removeChild(modalOverlay);
            }
        });
    }

    // Initialize download functionality when page loads
    initializeDownloadButtons();
});
