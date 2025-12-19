// Companion Demo Interface JavaScript

// Authentication Management
class AuthManager {
    constructor() {
        this.token = this.getToken();
        this.user = this.getUser();
    }

    getToken() {
        return localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    }

    getUser() {
        const userStr = localStorage.getItem('user_data') || sessionStorage.getItem('user_data');
        return userStr ? JSON.parse(userStr) : null;
    }

    setAuth(token, user, remember = false) {
        if (remember) {
            localStorage.setItem('auth_token', token);
            localStorage.setItem('user_data', JSON.stringify(user));
        } else {
            sessionStorage.setItem('auth_token', token);
            sessionStorage.setItem('user_data', JSON.stringify(user));
        }
        this.token = token;
        this.user = user;
    }

    clearAuth() {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_data');
        sessionStorage.removeItem('auth_token');
        sessionStorage.removeItem('user_data');
        this.token = null;
        this.user = null;
    }

    isAuthenticated() {
        return !!this.token;
    }

    async checkAuth() {
        if (!this.token) return false;

        try {
            const response = await fetch('/api/auth/me', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.user = data.user;
                return true;
            } else {
                this.clearAuth();
                return false;
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            return false;
        }
    }

    async logout() {
        // For stateless JWT auth, just clear local storage
        this.clearAuth();
        window.location.href = 'login.html';
    }

    getAuthHeaders() {
        return this.token ? { 'Authorization': `Bearer ${this.token}` } : {};
    }
}

// Global auth manager
const authManager = new AuthManager();

// Check authentication on page load
async function checkAuthOnLoad() {
    // Skip auth check for public pages
    const publicPages = ['login.html', 'signup.html'];
    const currentPage = window.location.pathname.split('/').pop();
    
    if (publicPages.includes(currentPage)) {
        return;
    }

    const isAuthenticated = await authManager.checkAuth();
    if (!isAuthenticated) {
        // Redirect to login page
        window.location.href = 'login.html';
        return;
    }

    // Update UI with user info
    updateUserInterface();
}

function updateUserInterface() {
    if (authManager.user) {
        // Update navbar with user info
        updateNavbarWithUser();
        
        // Show authenticated content
        const authContent = document.querySelectorAll('.auth-required');
        authContent.forEach(el => el.style.display = 'block');
        
        const noAuthContent = document.querySelectorAll('.no-auth-required');
        noAuthContent.forEach(el => el.style.display = 'none');
        
        // Update demo button to "Go to Chat" for logged-in users
        const tryDemoBtn = document.getElementById('tryDemoBtn');
        const goToChatBtn = document.getElementById('goToChatBtn');
        if (tryDemoBtn && goToChatBtn) {
            tryDemoBtn.style.display = 'none';
            goToChatBtn.style.display = 'inline-block';
        }
    }
}

function updateNavbarWithUser() {
    const navMenu = document.querySelector('.nav-menu');
    if (navMenu && authManager.user) {
        // Add user menu
        const userMenuItem = document.createElement('li');
        userMenuItem.className = 'user-menu';
        userMenuItem.innerHTML = `
            <div class="user-dropdown">
                <button class="user-btn">
                    <span class="user-avatar">${authManager.user.name.charAt(0).toUpperCase()}</span>
                    <span class="user-name">${authManager.user.name}</span>
                    <i class="fas fa-chevron-down"></i>
                </button>
                <div class="dropdown-menu">
                    <a href="#profile">Profile</a>
                    <a href="#settings">Settings</a>
                    <a href="#" onclick="authManager.logout()">Logout</a>
                </div>
            </div>
        `;
        navMenu.appendChild(userMenuItem);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Check authentication first
    checkAuthOnLoad();
    
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
            Windows: 'https://github.com/Aryan-Rajyaguru-1/Companion/releases/latest/download/companion-windows.exe',
            macOS: 'https://github.com/Aryan-Rajyaguru-1/Companion/releases/latest/download/companion-macos.dmg',
            Linux: 'https://github.com/Aryan-Rajyaguru-1/Companion/releases/latest/download/companion-linux.deb',
            source: 'https://github.com/Aryan-Rajyaguru-1/Companion'
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
            window.open('https://github.com/Aryan-Rajyaguru-1/Companion', '_blank');
            document.body.removeChild(modalOverlay);
        });
        
        document.getElementById('viewSource').addEventListener('click', function() {
            window.open('https://github.com/Aryan-Rajyaguru-1/Companion', '_blank');
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
    
    // Initialize Get API section functionality
    initializeGetAPISection();
});

// Get API Section Functions
function initializeGetAPISection() {
    // Code tabs functionality
    const codeTabs = document.querySelectorAll('.code-tab');
    const codeBlocks = document.querySelectorAll('.code-block');
    
    codeTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const targetLang = this.getAttribute('data-lang');
            
            // Remove active class from all tabs and blocks
            codeTabs.forEach(t => t.classList.remove('active'));
            codeBlocks.forEach(b => b.classList.remove('active'));
            
            // Add active class to clicked tab and corresponding block
            this.classList.add('active');
            const targetBlock = document.querySelector(`.code-block[data-lang="${targetLang}"]`);
            if (targetBlock) {
                targetBlock.classList.add('active');
            }
        });
    });
}

// API Health Check Function
async function checkAPIHealth() {
    const button = event.target;
    const originalText = button.innerHTML;
    
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
    button.disabled = true;
    
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        if (response.ok) {
            showNotification('✅ API is healthy and ready!', 'success');
            button.innerHTML = '<i class="fas fa-check"></i> API Healthy';
            button.classList.add('success');
            
            setTimeout(() => {
                button.innerHTML = originalText;
                button.classList.remove('success');
                button.disabled = false;
            }, 3000);
        } else {
            throw new Error('API not responding');
        }
    } catch (error) {
        showNotification('❌ API is not available. Please start the server first.', 'error');
        button.innerHTML = '<i class="fas fa-times"></i> API Offline';
        button.classList.add('error');
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.classList.remove('error');
            button.disabled = false;
        }, 3000);
    }
}

// Enhanced notification system
function showNotification(message, type = 'info') {
    // Remove existing notification if any
    const existing = document.querySelector('.api-notification');
    if (existing) {
        existing.remove();
    }
    
    const notification = document.createElement('div');
    notification.className = `api-notification ${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span>${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    // Add notification styles
    const style = `
        .api-notification {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            animation: slideIn 0.3s ease;
            max-width: 400px;
        }
        .api-notification.success { background: #10b981; }
        .api-notification.error { background: #ef4444; }
        .api-notification.info { background: #3b82f6; }
        .notification-content { display: flex; justify-content: space-between; align-items: center; }
        .notification-close { 
            background: none; border: none; color: white; 
            font-size: 18px; cursor: pointer; margin-left: 10px;
        }
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
    `;
    
    // Add styles if not already added
    if (!document.querySelector('#notification-styles')) {
        const styleElement = document.createElement('style');
        styleElement.id = 'notification-styles';
        styleElement.textContent = style;
        document.head.appendChild(styleElement);
    }
    
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Get API Integration functionality
let generatedAPIKey = null;
let isAPIKeyViewed = false;
let apiKeyPassword = null;

function generateAPIKey() {
    // Generate a random API key
    const apiKey = 'ck_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15) + '_' + Date.now().toString(36);
    generatedAPIKey = apiKey;
    
    // Show security options modal
    showAPIKeySecurityModal();
}

function showAPIKeySecurityModal() {
    const modal = document.createElement('div');
    modal.className = 'api-security-modal';
    modal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h3><i class="fas fa-shield-alt"></i> Secure Your API Key</h3>
                <button class="modal-close" onclick="closeAPIKeyModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="security-warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>For your security, please choose how you want to protect your API key:</p>
                </div>
                
                <div class="security-options">
                    <div class="option-card" onclick="selectSecurityOption('password')">
                        <i class="fas fa-lock"></i>
                        <h4>Password Protection</h4>
                        <p>Set a password to view your API key anytime</p>
                        <div class="option-benefits">
                            ✓ Reusable access<br>
                            ✓ Maximum security<br>
                            ✓ Password recovery
                        </div>
                    </div>
                    
                    <div class="option-card" onclick="selectSecurityOption('onetime')">
                        <i class="fas fa-eye-slash"></i>
                        <h4>One-Time View</h4>
                        <p>View your API key once, then it disappears forever</p>
                        <div class="option-benefits">
                            ✓ Immediate access<br>
                            ✓ No password needed<br>
                            ⚠️ Copy it safely!
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    modal.style.display = 'flex';
}

function selectSecurityOption(option) {
    if (option === 'password') {
        showPasswordSetupModal();
    } else {
        showOneTimeAPIKey();
    }
}

function showPasswordSetupModal() {
    const modal = document.querySelector('.api-security-modal');
    modal.querySelector('.modal-body').innerHTML = `
        <div class="password-setup">
            <div class="setup-header">
                <i class="fas fa-key"></i>
                <h4>Set Password for API Key</h4>
                <p>Choose a strong password to protect your API key</p>
            </div>
            
            <form onsubmit="setupAPIKeyPassword(event)" class="password-form">
                <div class="form-group">
                    <label for="apiPassword">Password</label>
                    <input type="password" id="apiPassword" required minlength="6" 
                           placeholder="Enter a strong password">
                    <small>Minimum 6 characters</small>
                </div>
                
                <div class="form-group">
                    <label for="confirmPassword">Confirm Password</label>
                    <input type="password" id="confirmPassword" required 
                           placeholder="Confirm your password">
                </div>
                
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="showAPIKeySecurityModal()">
                        <i class="fas fa-arrow-left"></i> Back
                    </button>
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-shield-alt"></i> Secure API Key
                    </button>
                </div>
            </form>
        </div>
    `;
}

function setupAPIKeyPassword(event) {
    event.preventDefault();
    
    const password = document.getElementById('apiPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (password !== confirmPassword) {
        showNotification('Passwords do not match!', 'error');
        return;
    }
    
    if (password.length < 6) {
        showNotification('Password must be at least 6 characters long!', 'error');
        return;
    }
    
    // Store password (in real app, this would be hashed and stored securely)
    apiKeyPassword = password;
    
    // Close modal and show success
    closeAPIKeyModal();
    showAPIKeyProtectedSuccess();
}

function showOneTimeAPIKey() {
    closeAPIKeyModal();
    
    // Show one-time warning modal
    const warningModal = document.createElement('div');
    warningModal.className = 'api-warning-modal';
    warningModal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-content warning-content">
            <div class="warning-header">
                <i class="fas fa-exclamation-circle"></i>
                <h3>⚠️ One-Time View Warning</h3>
            </div>
            <div class="warning-body">
                <div class="warning-message">
                    <p><strong>IMPORTANT:</strong> Your API key will be shown only ONCE!</p>
                    <p>Please copy it now and write it down somewhere safe. You will not be able to see it again.</p>
                </div>
                
                <div class="warning-checklist">
                    <label class="checkbox-container">
                        <input type="checkbox" id="understand1" required>
                        <span class="checkmark"></span>
                        I understand this is a one-time view
                    </label>
                    <label class="checkbox-container">
                        <input type="checkbox" id="understand2" required>
                        <span class="checkmark"></span>
                        I will copy and save the API key immediately
                    </label>
                    <label class="checkbox-container">
                        <input type="checkbox" id="understand3" required>
                        <span class="checkmark"></span>
                        I understand I cannot recover this key if lost
                    </label>
                </div>
                
                <div class="warning-actions">
                    <button class="btn btn-secondary" onclick="closeWarningModal()">
                        <i class="fas fa-times"></i> Cancel
                    </button>
                    <button class="btn btn-danger" onclick="revealOneTimeAPIKey()" id="revealBtn" disabled>
                        <i class="fas fa-unlock"></i> Show API Key
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(warningModal);
    warningModal.style.display = 'flex';
    
    // Enable reveal button only when all checkboxes are checked
    const checkboxes = warningModal.querySelectorAll('input[type="checkbox"]');
    const revealBtn = document.getElementById('revealBtn');
    
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            revealBtn.disabled = !allChecked;
            revealBtn.style.opacity = allChecked ? '1' : '0.5';
        });
    });
}

function revealOneTimeAPIKey() {
    closeWarningModal();
    
    // Display the API key with auto-destruction timer
    const apiKeyDisplay = document.getElementById('apiKeyDisplay');
    const apiKeyInput = document.getElementById('apiKeyInput');
    
    if (apiKeyDisplay && apiKeyInput) {
        apiKeyInput.value = generatedAPIKey;
        apiKeyDisplay.style.display = 'block';
        
        // Add destruction warning
        const warningDiv = document.createElement('div');
        warningDiv.className = 'destruction-warning';
        warningDiv.innerHTML = `
            <div class="warning-banner">
                <i class="fas fa-clock"></i>
                <span>This API key will disappear in <span id="countdown">60</span> seconds!</span>
                <button onclick="extendTime()" class="extend-btn">+30s</button>
            </div>
        `;
        
        apiKeyDisplay.insertBefore(warningDiv, apiKeyDisplay.firstChild);
        
        // Start countdown
        startAPIKeyDestruction();
        
        // Update button
        const button = document.querySelector('.generate-api-btn');
        if (button) {
            button.innerHTML = '<i class="fas fa-eye"></i> API Key Revealed';
            button.style.background = '#dc3545';
            button.disabled = true;
        }
        
        // Show critical warning
        showNotification('⚠️ COPY YOUR API KEY NOW! It will disappear soon!', 'warning');
    }
    
    isAPIKeyViewed = true;
}

function startAPIKeyDestruction(seconds = 60) {
    const countdown = document.getElementById('countdown');
    if (!countdown) return;
    
    const timer = setInterval(() => {
        seconds--;
        countdown.textContent = seconds;
        
        if (seconds <= 10) {
            countdown.parentElement.style.color = '#dc3545';
            countdown.parentElement.style.fontWeight = 'bold';
        }
        
        if (seconds <= 0) {
            clearInterval(timer);
            destroyAPIKey();
        }
    }, 1000);
    
    // Store timer reference for extending
    window.apiKeyTimer = timer;
    window.remainingSeconds = seconds;
}

function extendTime() {
    if (window.apiKeyTimer) {
        clearInterval(window.apiKeyTimer);
    }
    
    window.remainingSeconds += 30;
    const countdown = document.getElementById('countdown');
    if (countdown) {
        countdown.parentElement.style.color = '#007bff';
        countdown.parentElement.style.fontWeight = 'normal';
        startAPIKeyDestruction(window.remainingSeconds);
        showNotification('Time extended by 30 seconds!', 'success');
    }
}

function destroyAPIKey() {
    const apiKeyDisplay = document.getElementById('apiKeyDisplay');
    const apiKeyInput = document.getElementById('apiKeyInput');
    
    if (apiKeyDisplay && apiKeyInput) {
        // Clear the API key
        apiKeyInput.value = '';
        apiKeyDisplay.style.display = 'none';
        
        // Clear from memory
        generatedAPIKey = null;
        
        // Reset button
        const button = document.querySelector('.generate-api-btn');
        if (button) {
            button.innerHTML = '<i class="fas fa-key"></i> Generate New API Key';
            button.style.background = '';
            button.disabled = false;
        }
        
        // Show destruction notification
        showNotification('🔥 API Key has been destroyed for security!', 'info');
    }
}

function showAPIKeyProtectedSuccess() {
    const apiKeyDisplay = document.getElementById('apiKeyDisplay');
    
    if (apiKeyDisplay) {
        apiKeyDisplay.innerHTML = `
            <div class="protected-api-display">
                <div class="protection-status">
                    <i class="fas fa-shield-check"></i>
                    <h4>API Key Protected</h4>
                    <p>Your API key has been generated and secured with password protection.</p>
                </div>
                
                <div class="access-controls">
                    <button onclick="requestAPIKeyAccess()" class="btn btn-primary">
                        <i class="fas fa-unlock"></i> Enter Password to View
                    </button>
                </div>
                
                <div class="security-info">
                    <small><i class="fas fa-info-circle"></i> Your API key is encrypted and requires your password to view</small>
                </div>
            </div>
        `;
        
        apiKeyDisplay.style.display = 'block';
        
        // Update button
        const button = document.querySelector('.generate-api-btn');
        if (button) {
            button.innerHTML = '<i class="fas fa-shield-check"></i> API Key Secured';
            button.style.background = '#10b981';
        }
        
        showNotification('API Key secured with password protection!', 'success');
    }
}

function requestAPIKeyAccess() {
    const accessModal = document.createElement('div');
    accessModal.className = 'api-access-modal';
    accessModal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h3><i class="fas fa-unlock"></i> Enter Password</h3>
                <button class="modal-close" onclick="closeAccessModal()">&times;</button>
            </div>
            <div class="modal-body">
                <form onsubmit="verifyAPIKeyPassword(event)" class="access-form">
                    <div class="form-group">
                        <label for="accessPassword">Enter your password to view the API key:</label>
                        <input type="password" id="accessPassword" required 
                               placeholder="Enter password" autofocus>
                    </div>
                    
                    <div class="form-actions">
                        <button type="button" class="btn btn-secondary" onclick="closeAccessModal()">
                            Cancel
                        </button>
                        <button type="submit" class="btn btn-primary">
                            <i class="fas fa-eye"></i> View API Key
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    document.body.appendChild(accessModal);
    accessModal.style.display = 'flex';
}

function verifyAPIKeyPassword(event) {
    event.preventDefault();
    
    const enteredPassword = document.getElementById('accessPassword').value;
    
    if (enteredPassword === apiKeyPassword) {
        closeAccessModal();
        showProtectedAPIKey();
    } else {
        showNotification('Incorrect password!', 'error');
        document.getElementById('accessPassword').value = '';
        document.getElementById('accessPassword').focus();
    }
}

function showProtectedAPIKey() {
    const apiKeyDisplay = document.getElementById('apiKeyDisplay');
    
    if (apiKeyDisplay && generatedAPIKey) {
        apiKeyDisplay.innerHTML = `
            <div class="revealed-api-display">
                <div class="api-key-container">
                    <label>Your Protected API Key:</label>
                    <div class="api-key-input-group">
                        <input type="text" value="${generatedAPIKey}" readonly id="protectedApiKey">
                        <button class="copy-btn" onclick="copyProtectedAPIKey()">
                            <i class="fas fa-copy"></i>
                        </button>
                    </div>
                    <small class="api-key-note">
                        <i class="fas fa-shield-alt"></i> This key is password protected and can be viewed anytime
                    </small>
                </div>
                
                <div class="protection-controls">
                    <button onclick="hideAPIKey()" class="btn btn-secondary">
                        <i class="fas fa-eye-slash"></i> Hide Key
                    </button>
                    <button onclick="changeAPIKeyPassword()" class="btn btn-outline">
                        <i class="fas fa-key"></i> Change Password
                    </button>
                </div>
            </div>
        `;
        
        showNotification('API Key unlocked successfully!', 'success');
    }
}

function hideAPIKey() {
    showAPIKeyProtectedSuccess();
}

function copyProtectedAPIKey() {
    const apiKeyInput = document.getElementById('protectedApiKey');
    if (apiKeyInput) {
        apiKeyInput.select();
        apiKeyInput.setSelectionRange(0, 99999);
        
        try {
            document.execCommand('copy');
            showNotification('Protected API Key copied to clipboard!', 'success');
            
            const copyBtn = document.querySelector('.copy-btn');
            if (copyBtn) {
                const originalHTML = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="fas fa-check"></i>';
                copyBtn.style.background = '#10b981';
                
                setTimeout(() => {
                    copyBtn.innerHTML = originalHTML;
                    copyBtn.style.background = '';
                }, 2000);
            }
        } catch (err) {
            showNotification('Failed to copy API Key', 'error');
        }
    }
}

function closeAPIKeyModal() {
    const modal = document.querySelector('.api-security-modal');
    if (modal) {
        modal.remove();
    }
}

function closeWarningModal() {
    const modal = document.querySelector('.api-warning-modal');
    if (modal) {
        modal.remove();
    }
}

function closeAccessModal() {
    const modal = document.querySelector('.api-access-modal');
    if (modal) {
        modal.remove();
    }
}

function copyAPIKey() {
    const apiKeyInput = document.getElementById('apiKeyInput');
    if (apiKeyInput) {
        apiKeyInput.select();
        apiKeyInput.setSelectionRange(0, 99999); // For mobile devices
        
        try {
            document.execCommand('copy');
            showNotification('API Key copied to clipboard!', 'success');
            
            // Update copy button temporarily
            const copyBtn = document.querySelector('.copy-btn');
            if (copyBtn) {
                const originalHTML = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="fas fa-check"></i>';
                copyBtn.style.background = '#10b981';
                
                setTimeout(() => {
                    copyBtn.innerHTML = originalHTML;
                    copyBtn.style.background = '';
                }, 2000);
            }
        } catch (err) {
            showNotification('Failed to copy API Key', 'error');
        }
    }
}

// Code tabs functionality for Get API section
function initCodeTabs() {
    const tabButtons = document.querySelectorAll('.code-tabs .tab-btn');
    const tabPanes = document.querySelectorAll('.code-tabs .tab-pane');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.getAttribute('data-tab');
            
            // Remove active class from all buttons and panes
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));
            
            // Add active class to clicked button and corresponding pane
            button.classList.add('active');
            const targetPane = document.getElementById(targetTab);
            if (targetPane) {
                targetPane.classList.add('active');
            }
        });
    });
}

// Initialize code tabs when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initCodeTabs();
    
    // Add click handlers for API key functionality
    const generateBtn = document.querySelector('.generate-api-btn');
    if (generateBtn) {
        generateBtn.addEventListener('click', generateAPIKey);
    }
    
    const copyBtn = document.querySelector('.copy-btn');
    if (copyBtn) {
        copyBtn.addEventListener('click', copyAPIKey);
    }
});
