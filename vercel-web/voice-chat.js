/**
 * Voice Chat Module
 * Handles Speech-to-Text (STT) and Text-to-Speech (TTS) functionality
 */

class VoiceChat {
    constructor() {
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.isListening = false;
        this.isSpeaking = false;
        this.currentUtterance = null;
        
        // Check for browser support
        this.checkBrowserSupport();
        
        // Initialize Speech Recognition
        if (this.sttSupported) {
            this.initSpeechRecognition();
        }
        
        console.log('🎤 Voice Chat initialized:', {
            sttSupported: this.sttSupported,
            ttsSupported: this.ttsSupported
        });
    }
    
    checkBrowserSupport() {
        // Check STT support
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.sttSupported = !!SpeechRecognition;
        
        // Check TTS support
        this.ttsSupported = 'speechSynthesis' in window;
        
        // Store browser info for better error messages
        this.browserName = this.detectBrowser();
        
        if (!this.sttSupported) {
            console.warn('⚠️ Speech Recognition not supported in this browser');
            if (this.browserName === 'Firefox') {
                console.warn('💡 Voice input requires Chrome, Edge, or Safari');
            }
        }
        
        if (!this.ttsSupported) {
            console.warn('⚠️ Speech Synthesis not supported in this browser');
        }
    }
    
    detectBrowser() {
        const ua = navigator.userAgent;
        if (ua.indexOf('Firefox') > -1) return 'Firefox';
        if (ua.indexOf('Edg') > -1) return 'Edge';
        if (ua.indexOf('Chrome') > -1) return 'Chrome';
        if (ua.indexOf('Safari') > -1) return 'Safari';
        return 'Unknown';
    }
    
    initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        
        // Configuration
        this.recognition.continuous = false;  // Stop after one result
        this.recognition.interimResults = true;  // Show interim results
        this.recognition.lang = 'en-US';  // Default language
        this.recognition.maxAlternatives = 1;
        
        // Event handlers
        this.recognition.onstart = () => {
            console.log('🎤 Speech recognition started');
            this.isListening = true;
            this.onListeningStart();
        };
        
        this.recognition.onresult = (event) => {
            const results = event.results;
            const lastResult = results[results.length - 1];
            const transcript = lastResult[0].transcript;
            const isFinal = lastResult.isFinal;
            
            console.log(`🎤 ${isFinal ? 'Final' : 'Interim'} result:`, transcript);
            
            if (isFinal) {
                this.onTranscriptFinal(transcript);
            } else {
                this.onTranscriptInterim(transcript);
            }
        };
        
        this.recognition.onerror = (event) => {
            console.error('🎤 Speech recognition error:', event.error);
            this.isListening = false;
            this.onListeningError(event.error);
        };
        
        this.recognition.onend = () => {
            console.log('🎤 Speech recognition ended');
            this.isListening = false;
            this.onListeningEnd();
        };
    }
    
    // STT Methods
    startListening() {
        if (!this.sttSupported) {
            alert('Speech recognition is not supported in your browser. Please use Chrome or Edge.');
            return false;
        }
        
        if (this.isListening) {
            this.stopListening();
            return false;
        }
        
        try {
            this.recognition.start();
            return true;
        } catch (error) {
            console.error('Error starting speech recognition:', error);
            return false;
        }
    }
    
    stopListening() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
        }
    }
    
    // TTS Methods
    speak(text, options = {}) {
        if (!this.ttsSupported) {
            console.warn('Speech synthesis not supported');
            return false;
        }
        
        // Stop any ongoing speech
        this.stopSpeaking();
        
        // Create utterance
        this.currentUtterance = new SpeechSynthesisUtterance(text);
        
        // Configure utterance
        this.currentUtterance.rate = options.rate || 1.0;  // Speed (0.1 to 10)
        this.currentUtterance.pitch = options.pitch || 1.0;  // Pitch (0 to 2)
        this.currentUtterance.volume = options.volume || 1.0;  // Volume (0 to 1)
        this.currentUtterance.lang = options.lang || 'en-US';
        
        // Select voice if specified
        if (options.voice) {
            const voices = this.synthesis.getVoices();
            const selectedVoice = voices.find(v => v.name === options.voice);
            if (selectedVoice) {
                this.currentUtterance.voice = selectedVoice;
            }
        }
        
        // Event handlers
        this.currentUtterance.onstart = () => {
            console.log('🔊 Started speaking');
            this.isSpeaking = true;
            this.onSpeakingStart();
        };
        
        this.currentUtterance.onend = () => {
            console.log('🔊 Finished speaking');
            this.isSpeaking = false;
            this.onSpeakingEnd();
        };
        
        this.currentUtterance.onerror = (event) => {
            console.error('🔊 Speech synthesis error:', event);
            this.isSpeaking = false;
            this.onSpeakingError(event);
        };
        
        // Speak
        this.synthesis.speak(this.currentUtterance);
        return true;
    }
    
    stopSpeaking() {
        if (this.synthesis.speaking) {
            this.synthesis.cancel();
            this.isSpeaking = false;
        }
    }
    
    pauseSpeaking() {
        if (this.synthesis.speaking) {
            this.synthesis.pause();
        }
    }
    
    resumeSpeaking() {
        if (this.synthesis.paused) {
            this.synthesis.resume();
        }
    }
    
    // Get available voices
    getVoices() {
        return this.synthesis.getVoices();
    }
    
    // Get voices by language
    getVoicesByLanguage(lang) {
        return this.getVoices().filter(voice => voice.lang.startsWith(lang));
    }
    
    // Callback methods (to be overridden)
    onListeningStart() {
        // Override this method to handle listening start
    }
    
    onListeningEnd() {
        // Override this method to handle listening end
    }
    
    onListeningError(error) {
        // Override this method to handle errors
    }
    
    onTranscriptInterim(transcript) {
        // Override this method to handle interim results
    }
    
    onTranscriptFinal(transcript) {
        // Override this method to handle final results
    }
    
    onSpeakingStart() {
        // Override this method to handle speaking start
    }
    
    onSpeakingEnd() {
        // Override this method to handle speaking end
    }
    
    onSpeakingError(event) {
        // Override this method to handle speaking errors
    }
    
    // Language support
    setLanguage(lang) {
        if (this.recognition) {
            this.recognition.lang = lang;
        }
    }
    
    // Get supported languages
    getSupportedLanguages() {
        return [
            { code: 'en-US', name: 'English (US)' },
            { code: 'en-GB', name: 'English (UK)' },
            { code: 'es-ES', name: 'Spanish' },
            { code: 'fr-FR', name: 'French' },
            { code: 'de-DE', name: 'German' },
            { code: 'it-IT', name: 'Italian' },
            { code: 'pt-BR', name: 'Portuguese (Brazil)' },
            { code: 'ja-JP', name: 'Japanese' },
            { code: 'ko-KR', name: 'Korean' },
            { code: 'zh-CN', name: 'Chinese (Simplified)' },
            { code: 'hi-IN', name: 'Hindi' },
            { code: 'ar-SA', name: 'Arabic' },
            { code: 'ru-RU', name: 'Russian' }
        ];
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VoiceChat;
}
