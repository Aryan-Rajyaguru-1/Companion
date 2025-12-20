/**
 * DeepCompanion Testing Suite JavaScript
 * Interactive functionality for the AI model testing interface
 */

// Add error handling and logging
console.log('Loading DeepCompanion Testing Suite...');

class TestingSuite {
    constructor() {
        console.log('Initializing TestingSuite...');
        this.currentModel = 'chat';
        this.testResults = [];
        this.isRunning = false;
        this.testCounter = 0;
        
        try {
            this.init();
            console.log('TestingSuite initialized successfully');
        } catch (error) {
            console.error('Error initializing TestingSuite:', error);
        }
    }
    
    init() {
        console.log('Binding events...');
        try {
            this.bindEvents();
            this.updateMetrics();
            this.loadExamplePrompts();
            console.log('Events bound successfully');
        } catch (error) {
            console.error('Error in init:', error);
        }
    }
    
    bindEvents() {
        // Model selection
        document.querySelectorAll('.model-card').forEach(card => {
            card.addEventListener('click', (e) => this.selectModel(e));
        });
        
        // Configuration sliders
        document.getElementById('temperature')?.addEventListener('input', (e) => {
            this.updateSliderValue(e.target, 'temperature');
        });
        
        document.getElementById('maxTokens')?.addEventListener('input', (e) => {
            this.updateSliderValue(e.target, 'maxTokens');
        });
        
        // Quick tests
        document.querySelectorAll('.quick-test-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.runQuickTest(e));
        });
        
        // Input actions
        document.getElementById('loadExample')?.addEventListener('click', () => {
            this.showExamplesModal();
        });
        
        document.getElementById('clearInput')?.addEventListener('click', () => {
            this.clearInput();
        });
        
        document.getElementById('runTest')?.addEventListener('click', () => {
            this.runTest();
        });
        
        // Results actions
        document.getElementById('exportResults')?.addEventListener('click', () => {
            this.exportResults();
        });
        
        document.getElementById('clearResults')?.addEventListener('click', () => {
            this.clearResults();
        });
        
        // Modal events
        document.getElementById('closeModal')?.addEventListener('click', () => {
            this.hideExamplesModal();
        });
        
        // Example selection
        document.querySelectorAll('.example-item').forEach(item => {
            item.addEventListener('click', (e) => this.selectExample(e));
        });
        
        // Input character counting
        const testInput = document.getElementById('testInput');
        if (testInput) {
            testInput.addEventListener('input', () => this.updateInputStats());
            testInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    this.runTest();
                }
            });
        }
        
        // Modal backdrop click
        document.getElementById('examplesModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'examplesModal') {
                this.hideExamplesModal();
            }
        });
    }
    
    selectModel(event) {
        // Remove active class from all model cards
        document.querySelectorAll('.model-card').forEach(card => {
            card.classList.remove('active');
        });
        
        // Add active class to clicked card
        event.currentTarget.classList.add('active');
        
        // Update current model
        this.currentModel = event.currentTarget.dataset.model;
        
        // Update UI to reflect model change
        this.updateModelStatus();
    }
    
    updateModelStatus() {
        const models = {
            chat: { name: 'Chat AI', emoji: '💬', desc: 'Conversational responses' },
            think: { name: 'Think AI', emoji: '🤔', desc: 'Deep reasoning and analysis' },
            code: { name: 'Code AI', emoji: '💻', desc: 'Programming assistance' },
            advanced: { name: 'Advanced AI', emoji: '🧠', desc: 'Complex problem solving' }
        };
        
        const model = models[this.currentModel];
        console.log(`Selected model: ${model.name}`);
    }
    
    updateSliderValue(slider, type) {
        const valueDisplay = slider.parentElement.querySelector('.slider-value');
        if (valueDisplay) {
            valueDisplay.textContent = type === 'temperature' ? 
                parseFloat(slider.value).toFixed(1) : 
                slider.value;
        }
    }
    
    runQuickTest(event) {
        const testType = event.currentTarget.dataset.test;
        const prompts = this.getQuickTestPrompts();
        
        if (prompts[testType]) {
            document.getElementById('testInput').value = prompts[testType];
            this.updateInputStats();
            this.runTest();
        }
    }
    
    getQuickTestPrompts() {
        return {
            reasoning: "Solve this logic puzzle: If all roses are flowers and some flowers fade quickly, can we conclude that some roses fade quickly? Explain your reasoning step by step.",
            coding: "Write a Python function to find the longest palindromic substring in a given string. Include time complexity analysis and test cases.",
            creative: "Write a short story about a robot who discovers they can dream, but only in programming languages. Make it engaging and thoughtful.",
            analysis: "Analyze the potential impact of quantum computing on current cybersecurity practices. Consider both threats and opportunities.",
            math: "Solve this calculus problem: Find the derivative of f(x) = x³ + 2x² - 5x + 1, then find the critical points and determine their nature.",
            conversation: "Let's have a philosophical discussion about consciousness. Do you think artificial intelligence can truly be conscious, or is it just sophisticated pattern matching?"
        };
    }
    
    showExamplesModal() {
        document.getElementById('examplesModal').style.display = 'block';
    }
    
    hideExamplesModal() {
        document.getElementById('examplesModal').style.display = 'none';
    }
    
    selectExample(event) {
        const exampleText = event.currentTarget.textContent.split(': ')[1];
        if (exampleText) {
            document.getElementById('testInput').value = exampleText;
            this.updateInputStats();
            this.hideExamplesModal();
        }
    }
    
    clearInput() {
        document.getElementById('testInput').value = '';
        this.updateInputStats();
    }
    
    updateInputStats() {
        const input = document.getElementById('testInput');
        const text = input.value;
        const charCount = text.length;
        const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
        
        document.getElementById('charCount').textContent = `${charCount} / 4000`;
        document.getElementById('wordCount').textContent = `${wordCount} words`;
        
        // Update character count color based on length
        const charCountEl = document.getElementById('charCount');
        if (charCount > 3500) {
            charCountEl.style.color = '#ef4444';
        } else if (charCount > 3000) {
            charCountEl.style.color = '#f59e0b';
        } else {
            charCountEl.style.color = 'rgba(255, 255, 255, 0.6)';
        }
    }
    
    async runTest() {
        if (this.isRunning) return;
        
        const input = document.getElementById('testInput').value.trim();
        if (!input) {
            this.showError('Please enter a test prompt');
            return;
        }
        
        this.isRunning = true;
        this.updateRunButton(true);
        
        try {
            const startTime = Date.now();
            
            // Simulate API call with realistic delay
            const result = await this.simulateAPICall(input);
            
            const endTime = Date.now();
            const responseTime = endTime - startTime;
            
            // Add result to results container
            this.addTestResult({
                model: this.currentModel,
                input: input,
                output: result,
                responseTime: responseTime,
                timestamp: new Date(),
                tokens: this.estimateTokens(input + result)
            });
            
            this.testCounter++;
            this.updateMetrics();
            
        } catch (error) {
            this.showError('Test failed: ' + error.message);
        } finally {
            this.isRunning = false;
            this.updateRunButton(false);
        }
    }
    
    async simulateAPICall(input) {
        // Simulate realistic API delay
        const delay = 800 + Math.random() * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
        
        // Generate a realistic response based on the current model
        const responses = this.generateMockResponse(input, this.currentModel);
        return responses;
    }
    
    generateMockResponse(input, model) {
        const responses = {
            chat: `I understand you're asking about "${input.substring(0, 50)}...". Based on my analysis, I can provide you with a comprehensive response that addresses your question directly.\n\nThis is a simulated response that would typically come from the Chat AI model. In a real implementation, this would connect to your Ollama instance running the DeepSeek R1 model.\n\nThe response would be contextually relevant and conversational in nature, providing helpful information while maintaining an engaging dialogue flow.`,
            
            think: `Let me think through this step by step...\n\n🤔 **Initial Analysis:**\nYour query "${input.substring(0, 40)}..." requires careful consideration of multiple factors.\n\n**Step 1: Problem Decomposition**\nI need to break down the core components of your question.\n\n**Step 2: Reasoning Process**\nApplying logical frameworks and considering various perspectives.\n\n**Step 3: Synthesis**\nCombining insights to form a comprehensive answer.\n\n**Conclusion:**\nThis is a simulated deep reasoning response from the Think AI model. The actual model would provide detailed analytical thinking and step-by-step problem solving.`,
            
            code: `\`\`\`python\n# Based on your request: "${input.substring(0, 40)}..."\n# Here's a code solution:\n\ndef solve_problem():\n    \"\"\"\n    This is a simulated code response from the Code AI model.\n    In reality, this would generate actual working code.\n    \"\"\"\n    result = "simulated_solution"\n    return result\n\n# Example usage:\nif __name__ == "__main__":\n    answer = solve_problem()\n    print(f"Result: {answer}")\n\`\`\`\n\n**Explanation:**\nThis code demonstrates the approach to solving your problem. The Code AI model would provide production-ready code with proper error handling, documentation, and test cases.`,
            
            advanced: `🧠 **Advanced Analysis Response**\n\nYour complex query "${input.substring(0, 30)}..." requires sophisticated reasoning across multiple domains.\n\n**Multi-dimensional Analysis:**\n• Technical implications\n• Theoretical frameworks\n• Practical considerations\n• Potential edge cases\n\n**Advanced Reasoning:**\nThis simulated response represents the Advanced AI model's capability to handle complex, multi-faceted problems that require deep understanding and sophisticated reasoning.\n\n**Synthesis:**\nThe actual model would provide nuanced insights, connect disparate concepts, and offer innovative solutions to challenging problems.`
        };
        
        return responses[model] || responses.chat;
    }
    
    estimateTokens(text) {
        // Rough token estimation (1 token ≈ 4 characters)
        return Math.ceil(text.length / 4);
    }
    
    addTestResult(result) {
        this.testResults.push(result);
        
        const container = document.getElementById('resultsContainer');
        const noResults = container.querySelector('.no-results');
        
        if (noResults) {
            noResults.remove();
        }
        
        const resultElement = this.createResultElement(result);
        container.appendChild(resultElement);
        
        // Scroll to bottom
        container.scrollTop = container.scrollHeight;
    }
    
    createResultElement(result) {
        const div = document.createElement('div');
        div.className = 'test-result';
        
        const modelEmojis = {
            chat: '💬',
            think: '🤔',
            code: '💻',
            advanced: '🧠'
        };
        
        div.innerHTML = `
            <div class="result-header">
                <div class="result-model">
                    <span>${modelEmojis[result.model] || '🤖'}</span>
                    <span>${result.model.charAt(0).toUpperCase() + result.model.slice(1)} AI</span>
                </div>
                <div class="result-timestamp">${this.formatTime(result.timestamp)}</div>
            </div>
            <div class="result-input">${result.input}</div>
            <div class="result-output">${result.output}</div>
            <div class="result-metrics">
                <div class="result-metric">
                    <span>⏱️</span>
                    <span class="metric-value">${result.responseTime}ms</span>
                </div>
                <div class="result-metric">
                    <span>🎯</span>
                    <span class="metric-value">${result.tokens} tokens</span>
                </div>
                <div class="result-metric">
                    <span>📊</span>
                    <span class="metric-value">Test #${this.testCounter}</span>
                </div>
            </div>
        `;
        
        return div;
    }
    
    formatTime(date) {
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
    
    updateRunButton(isLoading) {
        const button = document.getElementById('runTest');
        const icon = button.querySelector('.run-icon');
        
        if (isLoading) {
            button.classList.add('loading');
            button.innerHTML = '<span>Running Test...</span><span class="loading-spinner"></span>';
            button.disabled = true;
        } else {
            button.classList.remove('loading');
            button.innerHTML = '<span>Run Test</span><span class="run-icon">🚀</span>';
            button.disabled = false;
        }
    }
    
    updateMetrics() {
        const totalTests = this.testResults.length;
        const avgResponseTime = totalTests > 0 ? 
            this.testResults.reduce((sum, result) => sum + result.responseTime, 0) / totalTests : 0;
        const totalTokens = this.testResults.reduce((sum, result) => sum + result.tokens, 0);
        
        document.getElementById('testsRun').textContent = totalTests;
        document.getElementById('avgResponse').textContent = avgResponseTime > 0 ? 
            `${(avgResponseTime / 1000).toFixed(1)}s` : '0s';
        document.getElementById('tokensUsed').textContent = totalTokens.toLocaleString();
        document.getElementById('successRate').textContent = '100%';
        
        // Update header status
        document.getElementById('responseTime').textContent = avgResponseTime > 0 ? 
            `~${(avgResponseTime / 1000).toFixed(1)}s` : '~0s';
    }
    
    clearResults() {
        if (confirm('Are you sure you want to clear all test results?')) {
            this.testResults = [];
            this.testCounter = 0;
            
            const container = document.getElementById('resultsContainer');
            container.innerHTML = `
                <div class="no-results">
                    <div class="no-results-icon">🧪</div>
                    <h4>No tests run yet</h4>
                    <p>Start by entering a test prompt and clicking "Run Test" or try one of the quick tests.</p>
                </div>
            `;
            
            this.updateMetrics();
        }
    }
    
    exportResults() {
        if (this.testResults.length === 0) {
            this.showError('No test results to export');
            return;
        }
        
        const data = {
            exportDate: new Date().toISOString(),
            totalTests: this.testResults.length,
            results: this.testResults.map(result => ({
                model: result.model,
                input: result.input,
                output: result.output,
                responseTime: result.responseTime,
                tokens: result.tokens,
                timestamp: result.timestamp.toISOString()
            }))
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `deepcompanion-test-results-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    showError(message) {
        // Create a temporary error message
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = `
            position: fixed;
            top: 100px;
            right: 20px;
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            z-index: 1001;
            animation: slideIn 0.3s ease;
        `;
        errorDiv.textContent = message;
        
        document.body.appendChild(errorDiv);
        
        setTimeout(() => {
            errorDiv.remove();
        }, 3000);
    }
    
    loadExamplePrompts() {
        // This could load example prompts from an API or local storage
        console.log('Example prompts loaded');
    }
}

// Initialize the testing suite when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing TestingSuite...');
    try {
        new TestingSuite();
    } catch (error) {
        console.error('Failed to initialize TestingSuite:', error);
        // Show a basic error message
        document.body.innerHTML = `
            <div style="padding: 40px; text-align: center; color: white; background: #0a0a12; min-height: 100vh;">
                <h1>DeepCompanion Testing Suite</h1>
                <p style="color: #ff5252; margin: 20px 0;">Error loading the testing interface.</p>
                <p>Please check the browser console for details.</p>
                <button onclick="location.reload()" style="padding: 10px 20px; margin-top: 20px; background: #7877c6; color: white; border: none; border-radius: 5px; cursor: pointer;">Reload Page</button>
            </div>
        `;
    }
});

// Add CSS for animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);
