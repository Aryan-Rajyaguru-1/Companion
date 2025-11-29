#!/usr/bin/env python3
"""
Companion Chat Backend
Handles chat history, conversations, and AI responses for the web interface
"""

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import json
import os
import sys
import uuid
from datetime import datetime, timedelta
import sqlite3
import logging
import requests as pyrequests
import urllib.parse
import re
import time
import threading
import schedule

# Import the unified API wrapper
from api_wrapper import api_wrapper, generate_companion_response, APIResponse

# Import the advanced search engine wrapper (for backwards compatibility)
from search_engine_wrapper import search_wrapper, SearchResult

# Import authentication system
from auth_backend import auth_manager

# Import response caching system
from response_cache import response_cache, start_cache_cleanup_thread

# NLP and ML imports
try:
    import nltk
    from textblob import TextBlob
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    NLP_AVAILABLE = True
    
    # Download required NLTK data
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)
        
    try:
        nltk.data.find('taggers/averaged_perceptron_tagger')
    except LookupError:
        nltk.download('averaged_perceptron_tagger', quiet=True)
        
except ImportError as e:
    logger.warning(f"NLP libraries not available: {e}")
    NLP_AVAILABLE = False

# Add parent directory to path to import the OpenRouter client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openrouter_client import OpenRouterClient
from config import get_openrouter_headers, get_model_config, OPENROUTER_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Neural Layer Pipeline (after logger is configured)
try:
    from neural_layers.neural_pipeline import LaptopNeuralPipeline
    NEURAL_LAYER_AVAILABLE = True
    logger.info("🧠 Neural layer imported successfully")
except ImportError as e:
    NEURAL_LAYER_AVAILABLE = False
    logger.warning(f"⚠️ Neural layer not available: {e}")

# Global neural pipeline instance
neural_pipeline = None

app = Flask(__name__, template_folder='.')
# Configure CORS to allow devtunnel and local origins
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:*",
            "http://127.0.0.1:*",
            "http://192.168.*.*:*",
            "https://*.devtunnels.ms",
            "https://*.inc1.devtunnels.ms"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Authentication middleware
def require_auth(f):
    """Decorator to require authentication for protected endpoints"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401
        
        token = auth_header.split(' ')[1]
        user = auth_manager.get_user_by_token(token)
        
        if not user:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Add user to request context
        request.current_user = user
        return f(*args, **kwargs)
    
    return decorated_function

# Authentication routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()
        
        # Extract data
        email = data.get('email', '').strip().lower()
        name = data.get('name', '').strip()
        password = data.get('password', '')
        newsletter = data.get('newsletter', False)
        
        # Get client info
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        # Register user
        success, message, user_data = auth_manager.register_user(
            email, name, password, newsletter
        )
        
        if success:
            logger.info(f"✅ New user registered: {email}")
            return jsonify({
                'success': True,
                'message': message,
                'user': {
                    'id': user_data['user_id'],
                    'email': email,
                    'name': name
                }
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({
            'success': False,
            'message': 'Registration failed due to server error'
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        
        # Extract data
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        remember = data.get('remember', False)
        
        # Get client info
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        # Authenticate user
        success, message, auth_data = auth_manager.login_user(
            email, password, ip_address, user_agent, remember
        )
        
        if success:
            logger.info(f"✅ User logged in: {email}")
            return jsonify({
                'success': True,
                'message': message,
                'token': auth_data['token'],
                'user': auth_data['user']
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 401
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            'success': False,
            'message': 'Login failed due to server error'
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """User logout endpoint"""
    try:
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ')[1]
        
        success = auth_manager.logout_user(token)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Logged out successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Logout failed'
            }), 500
            
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({
            'success': False,
            'message': 'Logout failed due to server error'
        }), 500

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def get_current_user():
    """Get current user information"""
    try:
        return jsonify({
            'success': True,
            'user': request.current_user
        }), 200
        
    except Exception as e:
        logger.error(f"Get user error: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to get user information'
        }), 500

@app.route('/api/auth/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change user password"""
    try:
        data = request.get_json()
        
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        success, message = auth_manager.change_password(
            request.current_user['id'], old_password, new_password
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        logger.error(f"Change password error: {e}")
        return jsonify({
            'success': False,
            'message': 'Password change failed due to server error'
        }), 500

# Initialize OpenRouter client
openrouter_client = OpenRouterClient()

# Database setup
DATABASE = 'chat_history.db'
KNOWLEDGE_CACHE = {}  # Cache for frequently accessed information
TRENDING_TOPICS = []  # Cache for trending topics
LAST_UPDATE = None    # Track when data was last updated

def startup_data_gathering():
    """Gather initial data on startup to improve response quality"""
    global KNOWLEDGE_CACHE, TRENDING_TOPICS, LAST_UPDATE
    
    logger.info("🚀 Starting data gathering for enhanced responses...")
    
    try:
        # Enhanced tech sources with DIVERSE topics across all domains
        tech_sources = [
            # AI & Technology
            "artificial intelligence news 2024 2025",
            "latest AI breakthroughs recent", 
            "machine learning trends current",
            
            # Programming & Development
            "programming trends 2024 2025",
            "software development latest",
            "web development trends current",
            "Python programming updates 2024",
            "JavaScript frameworks 2024 2025",
            "React Next.js updates current",
            
            # Business & Industry
            "tech industry news today",
            "startup technology trends 2024",
            "business technology innovations",
            "enterprise software trends current",
            
            # Science & Research
            "scientific breakthroughs 2024 2025",
            "medical technology advances recent",
            "space technology news current",
            "climate technology innovations",
            
            # Social & Cultural
            "social media trends 2024 2025",
            "digital culture trends current",
            "remote work technology trends",
            "education technology updates",
            
            # Security & Privacy
            "cybersecurity trends current 2024",
            "privacy technology news recent",
            "data protection innovations",
            
            # Hardware & Infrastructure
            "computer hardware trends 2024",
            "cloud computing advances recent",
            "mobile technology updates current",
            "gaming technology trends 2024",
            
            # Finance & Economy
            "fintech innovations 2024 2025",
            "cryptocurrency blockchain news",
            "digital payments technology trends",
            
            # Environmental & Sustainability
            "green technology innovations 2024",
            "renewable energy tech advances",
            "sustainable technology trends",
            
            # Emerging Technologies
            "quantum computing developments 2024",
            "virtual reality AR technology trends",
            "IoT internet of things updates",
            "autonomous vehicles technology news"
        ]
        
        successful_queries = 0
        
        for topic in tech_sources:
            try:
                # Enhanced DuckDuckGo query with better parameters
                ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(topic)}&format=json&no_redirect=1&no_html=1&skip_disambig=1&t=a"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9'
                }
                response = pyrequests.get(ddg_url, headers=headers, timeout=10)
                
                logger.info(f"🔍 Querying: {topic} - Status: {response.status_code}")
                
                if response.status_code in [200, 202]:
                    try:
                        data = response.json()
                        logger.info(f"📊 Response keys: {list(data.keys()) if data else 'Empty response'}")
                        
                        # Extract and cache relevant information with better error handling
                        cached_data = {}
                        
                        if data.get('AbstractText'):
                            abstract = data.get('AbstractText', '').strip()
                            if len(abstract) > 20:  # Only cache substantial content
                                cached_data['abstract'] = abstract
                                cached_data['source'] = data.get('AbstractSource', '')
                                cached_data['url'] = data.get('AbstractURL', '')
                                successful_queries += 1
                                logger.info(f"✅ Cached abstract for: {topic}")
                        
                        if data.get('Answer'):
                            answer = data.get('Answer', '').strip()
                            if len(answer) > 10:
                                cached_data['answer'] = answer
                                logger.info(f"✅ Cached answer for: {topic}")
                        
                        if data.get('Definition'):
                            definition = data.get('Definition', '').strip()
                            if len(definition) > 20:
                                cached_data['definition'] = definition
                                cached_data['def_source'] = data.get('DefinitionSource', '')
                                logger.info(f"✅ Cached definition for: {topic}")
                        
                        # Store if we have any useful data
                        if cached_data:
                            cached_data['timestamp'] = datetime.now().isoformat()
                            KNOWLEDGE_CACHE[topic] = cached_data
                        
                        # Extract trending topics from related topics with better filtering
                        related = data.get('RelatedTopics', [])
                        if related:
                            for item in related[:5]:  # Take top 5
                                if isinstance(item, dict):
                                    text = item.get('Text', '').strip()
                                    if (len(text) > 30 and len(text) < 200 and 
                                        text not in TRENDING_TOPICS and
                                        not any(skip_word in text.lower() for skip_word in ['wikipedia', 'wikimedia', 'disambiguation'])):
                                        TRENDING_TOPICS.append(text)
                                        logger.info(f"📈 Added trending: {text[:50]}...")
                        
                        # Extract from Results section if available
                        results = data.get('Results', [])
                        for result in results[:3]:
                            if isinstance(result, dict) and result.get('Text'):
                                text = result.get('Text', '').strip()
                                if (len(text) > 30 and len(text) < 200 and 
                                    text not in TRENDING_TOPICS):
                                    TRENDING_TOPICS.append(text)
                                    logger.info(f"📈 Added from results: {text[:50]}...")
                    
                    except Exception as json_error:
                        logger.warning(f"JSON parsing error for {topic}: {json_error}")
                        # Try alternative sources for this topic
                        try:
                            # Fallback: try a more general query
                            fallback_query = topic.split()[0] + " " + topic.split()[-1]
                            fallback_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(fallback_query)}&format=json"
                            fallback_resp = pyrequests.get(fallback_url, headers=headers, timeout=8)
                            if fallback_resp.status_code == 200:
                                fallback_data = fallback_resp.json()
                                if fallback_data.get('RelatedTopics'):
                                    for item in fallback_data['RelatedTopics'][:3]:
                                        if isinstance(item, dict) and item.get('Text'):
                                            text = item['Text'].strip()
                                            if len(text) > 30 and text not in TRENDING_TOPICS:
                                                TRENDING_TOPICS.append(text)
                                                logger.info(f"📈 Fallback trending: {text[:50]}...")
                        except Exception as fallback_error:
                            logger.warning(f"Fallback failed for {topic}: {fallback_error}")
                
                else:
                    logger.warning(f"❌ Failed query for {topic}: HTTP {response.status_code}")
                
                time.sleep(1.5)  # Increased rate limiting for better success
                
            except Exception as e:
                logger.warning(f"❌ Error gathering data for {topic}: {e}")
                continue
        
        # Add some hardcoded trending topics if we didn't get enough
        if len(TRENDING_TOPICS) < 5:
            fallback_topics = [
                "Artificial Intelligence advances in 2024-2025 including GPT-5, Claude 3.5, and multimodal AI capabilities",
                "Programming language trends: Python, JavaScript, TypeScript, Rust, and Go gaining popularity for modern development",
                "Web development evolution with React 19, Next.js 15, Vue 3, and serverless architecture innovations",
                "Machine Learning breakthroughs in computer vision, natural language processing, and reinforcement learning",
                "Cybersecurity developments including zero-trust architecture, AI-powered threat detection, and quantum cryptography",
                "Cloud computing advances with AWS, Azure, Google Cloud expanding AI/ML services and edge computing",
                "Mobile development trends including Flutter 3, React Native improvements, and cross-platform solutions",
                "DevOps evolution with Kubernetes, Docker, CI/CD automation, and infrastructure as code practices"
            ]
            
            for topic in fallback_topics:
                if topic not in TRENDING_TOPICS:
                    TRENDING_TOPICS.append(topic)
            
            logger.info(f"📝 Added {len(fallback_topics)} fallback trending topics")
        
        # Limit trending topics to most relevant ones
        TRENDING_TOPICS = TRENDING_TOPICS[:25]  # Increased limit
        LAST_UPDATE = datetime.now()
        
        logger.info(f"📊 Data gathering complete. Cached {len(KNOWLEDGE_CACHE)} topics, {len(TRENDING_TOPICS)} trending items")
        logger.info(f"✅ Successful queries: {successful_queries}/{len(tech_sources)}")
        
        # Log sample data for verification
        if KNOWLEDGE_CACHE:
            sample_topic = list(KNOWLEDGE_CACHE.keys())[0]
            logger.info(f"📄 Sample cached data for '{sample_topic}': {str(KNOWLEDGE_CACHE[sample_topic])[:100]}...")
        
        if TRENDING_TOPICS:
            logger.info(f"🔥 Sample trending topic: {TRENDING_TOPICS[0][:100]}...")
        
    except Exception as e:
        logger.error(f"❌ Critical error in startup data gathering: {e}")
        # Ensure we have some basic data even if gathering fails
        TRENDING_TOPICS = [
            "AI technology rapidly advancing with new language models and multimodal capabilities",
            "Programming trends shifting toward Python, TypeScript, and modern web frameworks",
            "Cybersecurity becoming crucial with increasing digital transformation and remote work",
            "Cloud computing expanding with serverless architectures and edge computing solutions",
            "Machine learning integration growing across industries for automation and insights"
        ]
        LAST_UPDATE = datetime.now()
        logger.info(f"🔄 Fallback: Added {len(TRENDING_TOPICS)} basic trending topics")

def update_knowledge_cache():
    """Periodically update knowledge cache"""
    threading.Thread(target=startup_data_gathering, daemon=True).start()

def enhanced_response_with_cache(message):
    """Use cached knowledge to enhance responses"""
    global KNOWLEDGE_CACHE, TRENDING_TOPICS
    
    message_lower = message.lower()
    enhanced_info = []
    
    # Check if user query matches cached knowledge
    for topic, data in KNOWLEDGE_CACHE.items():
        if any(word in topic.lower() for word in message_lower.split()):
            enhanced_info.append(f"📊 **Latest on {topic.title()}:** {data['abstract']}")
            if data.get('source'):
                enhanced_info.append(f"*Source: {data['source']}*")
    
    # Add trending topics if relevant
    if any(word in message_lower for word in ['trend', 'latest', 'new', 'recent', 'current']):
        if TRENDING_TOPICS:
            enhanced_info.append("🔥 **Current Trending Topics:**")
            for i, topic in enumerate(TRENDING_TOPICS[:5], 1):
                enhanced_info.append(f"{i}. {topic}")
    
    return "\n".join(enhanced_info) if enhanced_info else None

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT DEFAULT 'web_user'
        )
    ''')
    
    # Create messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            feedback_rating INTEGER DEFAULT NULL,
            feedback_comment TEXT DEFAULT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    ''')
    
    # Create adaptive learning table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_data (
            id TEXT PRIMARY KEY,
            question_pattern TEXT NOT NULL,
            successful_response TEXT NOT NULL,
            feedback_score REAL NOT NULL,
            usage_count INTEGER DEFAULT 1,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create feedback table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages (id),
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def generate_chat_title(message):
    """Generate a title for the chat based on the first message"""
    # Simple title generation - first 50 characters
    title = message.strip()[:50]
    if len(message) > 50:
        title += "..."
    return title

def scrape_web_content(url, max_length=1000):
    """Scrape content from a web URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = pyrequests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            # Try to extract text content
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Truncate if too long
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            return text
        else:
            return f"Failed to fetch content (Status: {response.status_code})"
    except ImportError:
        return "Web scraping requires BeautifulSoup4. Content preview not available."
    except Exception as e:
        return f"Error scraping content: {str(e)}"

def extract_thinking_data(response_text):
    """Extract thinking process from AI response (particularly DeepSeek R1)"""
    try:
        # Look for thinking patterns in the response
        thinking_patterns = [
            r'<thinking>(.*?)</thinking>',
            r'<think>(.*?)</think>',
            r'\*\*Thinking:\*\*(.*?)(?=\*\*[A-Z]|\n\n|\Z)',
            r'Let me think through this step by step:(.*?)(?=\n\n|\Z)',
            r'Step-by-step reasoning:(.*?)(?=\n\n|\Z)',
            r'My reasoning process:(.*?)(?=\n\n|\Z)',
            r'Analysis:(.*?)(?=\n\n|\Z)',
            r'Reasoning:(.*?)(?=\n\n|\Z)'
        ]
        
        for pattern in thinking_patterns:
            import re
            matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if matches:
                thinking_content = matches[0].strip()
                if len(thinking_content) > 30:  # Only return substantial thinking content
                    logger.info(f"🧠 Found thinking pattern: {pattern[:20]}...")
                    return thinking_content
        
        # For DeepSeek R1, also check for step-by-step reasoning patterns
        step_patterns = [
            r'(Step \d+:.*?)(?=Step \d+:|$)',
            r'(First[,:].*?)(?=Second[,:]|Next[,:]|$)',
            r'(\d+\.\s+.*?)(?=\d+\.\s+|$)'
        ]
        
        for pattern in step_patterns:
            matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if len(matches) >= 2:  # At least 2 steps
                thinking_content = '\n'.join(matches[:5])  # Take first 5 steps
                if len(thinking_content) > 50:
                    logger.info(f"🧠 Found step-by-step reasoning: {len(matches)} steps")
                    return thinking_content
        
        # Check for reasoning keywords that indicate thinking process
        reasoning_keywords = ['analyze', 'consider', 'think through', 'reasoning', 'step by step', 'let me break']
        lines = response_text.split('\n')
        thinking_lines = []
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if any(keyword in line_lower for keyword in reasoning_keywords):
                # Collect this line and a few following lines
                thinking_section = lines[i:min(i+10, len(lines))]
                thinking_content = '\n'.join(thinking_section).strip()
                if len(thinking_content) > 100:
                    logger.info(f"🧠 Found reasoning keywords section")
                    return thinking_content
                break
        
        # For DeepSeek R1, try to extract the first substantial paragraph that looks like reasoning
        paragraphs = [p.strip() for p in response_text.split('\n\n') if p.strip()]
        for para in paragraphs:
            if len(para) > 100 and any(word in para.lower() for word in ['because', 'since', 'therefore', 'thus', 'due to', 'given that', 'considering']):
                logger.info(f"🧠 Found reasoning paragraph")
                return para
                
        return None
    except Exception as e:
        logger.warning(f"Error extracting thinking data: {e}")
        return None

def clean_llm_tokens(text):
    """Remove special LLM tokens and artifacts from response text"""
    import re
    if not isinstance(text, str):
        text = str(text)
    
    # Remove various token formats
    patterns = [
        r'<[｜|]\s*\w+[▁_]\w+[▁_]*\w*\s*[｜|]>',  # <｜begin▁of▁sentence｜>
        r'<\|begin_of_sentence\|>',  # <|begin_of_sentence|>
        r'<\|end_of_sentence\|>',
        r'<\|begin_of_text\|>',
        r'<\|end_of_text\|>',
        r'<s>',  # Start of sequence
        r'</s>',  # End of sequence
        r'<pad>',
        r'<unk>',
        r'\[INST\]',
        r'\[/INST\]',
        r'APIResponse\(.*?\)',  # Remove APIResponse wrapper
    ]
    
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Remove any "content='" wrapper if present
    cleaned = re.sub(r"content='(.*?)'", r'\1', cleaned, flags=re.DOTALL)
    
    return cleaned.strip()

def generate_ai_response(message, conversation_id=None, chat_history=None, active_tools=None):
    """Generate AI response using the unified API wrapper with neural layer"""
    try:
        # Check for learned responses first
        learned_response = find_learned_response(message)
        if learned_response:
            return clean_llm_tokens(learned_response)
        
        if active_tools is None:
            active_tools = []
        
        # Auto-enable web search for "Who is..." queries about people
        who_is_pattern = r'(?i)who\s+is\s+([a-z\s]+?)(?:\?|$)'
        if re.search(who_is_pattern, message) and 'web' not in active_tools:
            logger.info(f"🔍 Auto-enabling web search for 'Who is...' query")
            active_tools.append('web')
        
        # Check cache first (skip cache for chat history-dependent queries)
        cache_context = {
            'tools': sorted(active_tools),  # Sort for consistent hashing
            'has_history': bool(chat_history and len(chat_history) > 0)
        }
        
        cached_response = response_cache.get(message, cache_context)
        if cached_response:
            logger.info(f"⚡ Using cached response for query: {message[:50]}...")
            return cached_response.get('content', cached_response)
        
        # Try Neural Layer Processing first (if available and enabled)
        # Skip neural layer if web/research tools are active (neural layer doesn't support tool routing yet)
        skip_neural = any(tool in active_tools for tool in ['web', 'deepsearch', 'research'])
        
        if NEURAL_LAYER_AVAILABLE and neural_pipeline is not None and not skip_neural:
            try:
                logger.info(f"🧠 Processing query through Neural Layer...")
                
                # Use neural pipeline for intelligent processing
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                neural_result = loop.run_until_complete(
                    neural_pipeline.process_query(message, use_neural=True)
                )
                loop.close()
                
                if neural_result and neural_result.get('response'):
                    logger.info(f"✅ Neural layer processed query successfully")
                    logger.info(f"📊 Neural stats: {neural_result.get('metadata', {})}")
                    
                    # If neural layer provided a response, use it
                    neural_response = neural_result['response']
                    metadata = neural_result.get('metadata', {})
                    
                    # Clean special tokens and artifacts from neural response
                    neural_response = clean_llm_tokens(neural_response)
                    
                    # Add metadata footer
                    footer = f"\n\n*🧠 Processed via Neural Layer"
                    if metadata.get('cache_hits', 0) > 0:
                        footer += f" • {metadata['cache_hits']} cache hits"
                    if metadata.get('processing_time'):
                        footer += f" • {metadata['processing_time']}"
                    footer += "*"
                    
                    final_neural_response = neural_response + footer
                    
                    # Cache neural response
                    cache_ttl = 1800 if chat_history and len(chat_history) > 0 else 3600
                    response_cache.set(message, final_neural_response, cache_context, ttl=cache_ttl)
                    logger.debug(f"💾 Neural response cached (ttl={cache_ttl}s)")
                    
                    return final_neural_response
                else:
                    logger.info("🔄 Neural layer returned no response, falling back to API wrapper")
            
            except Exception as neural_error:
                logger.warning(f"⚠️ Neural layer error: {neural_error}, falling back to API wrapper")
        
        logger.info(f"🎯 Using Companion API Wrapper with tools: {active_tools}")
        
        # Use the unified API wrapper for all responses
        response = generate_companion_response(
            message=message,
            tools=active_tools,
            chat_history=chat_history or []
        )
        
        if response.success:
            # Build final response with Companion branding
            final_response = response.content
            
            # Clean special tokens and artifacts from response
            final_response = clean_llm_tokens(final_response)
            
            # Add thinking data if available (for reasoning models)
            if response.thinking_data and 'think' in active_tools:
                thinking_cleaned = clean_llm_tokens(response.thinking_data)
                final_response = f"🧠 **Thinking Process:**\n{thinking_cleaned}\n\n---\n\n{final_response}"
            
            # Add reference links if available
            if response.links:
                final_response += "\n\n📚 **Reference Links:**\n"
                for i, link in enumerate(response.links[:5], 1):
                    final_response += f"{i}. **{link['title']}**\n   🔗 {link['url']}\n"
            
            # Add unified branding
            final_response += f"\n\n*Powered by Companion*"
            
            logger.info(f"✅ Generated response using {response.model} via {response.source}")
            
            # Cache the response (with shorter TTL for chat history-dependent queries)
            cache_ttl = 1800 if chat_history and len(chat_history) > 0 else 3600  # 30 min vs 1 hour
            response_cache.set(message, final_response, cache_context, ttl=cache_ttl)
            logger.debug(f"💾 Response cached (ttl={cache_ttl}s)")
            
            return final_response
            
        else:
            # Enhanced fallback with web scraping for research mode
            logger.error(f"❌ API wrapper failed: {response.error}")
            if 'research' in active_tools or 'deepsearch' in active_tools:
                # Try comprehensive web search as fallback for research queries
                try:
                    logger.info("🔍 Using enhanced web search fallback for research query")
                    search_data = search_wrapper.enhanced_search_with_mining(message, deep_search=True)
                    
                    if search_data and search_data['results']:
                        # Build comprehensive research response
                        web_parts = []
                        
                        # Add summary
                        if search_data.get('summary'):
                            web_parts.append(f"📖 **Research Summary:**\n{search_data['summary']}")
                        
                        # Add key facts
                        if search_data.get('key_facts'):
                            web_parts.append(f"💡 **Key Facts Discovered:**")
                            for i, fact in enumerate(search_data['key_facts'][:7], 1):
                                web_parts.append(f"{i}. {fact}")
                        
                        # Add search results with content previews
                        if search_data['results']:
                            web_parts.append(f"🔍 **Comprehensive Research Results ({len(search_data['sources'])} sources):**")
                            for i, result in enumerate(search_data['results'][:8], 1):
                                web_parts.append(f"**{i}. {result.title}** (via {result.source})")
                                if result.snippet:
                                    web_parts.append(f"   {result.snippet}")
                                if result.content and len(result.content) > 100:
                                    web_parts.append(f"   📄 *Preview:* {result.content[:200]}...")
                        
                        # Add related topics
                        if search_data.get('related_topics'):
                            web_parts.append(f"🔗 **Related Research Topics:**")
                            for topic in search_data['related_topics'][:10]:
                                web_parts.append(f"• {topic}")
                        
                        research_response = "🌐 **Deep Research Mode - Web Analysis:**\n\n" + "\n\n".join(web_parts)
                        
                        # Add reference links
                        if search_data.get('source_urls'):
                            research_response += "\n\n📚 **Research Sources:**\n"
                            for i, url in enumerate([url for url in search_data['source_urls'] if url][:8], 1):
                                title = next((r.title for r in search_data['results'] if r.url == url), f"Source {i}")
                                research_response += f"{i}. **{title}**\n   🔗 {url}\n"
                        
                        research_response += f"\n\n*Research conducted across {len(search_data['sources'])} search engines*"
                        
                        logger.info(f"✅ Research fallback: {len(search_data['results'])} results with content analysis")
                        return research_response
                    
                except Exception as web_error:
                    logger.error(f"❌ Web search fallback failed: {web_error}")
            
            return generate_intelligent_fallback_response(message, chat_history)
        
    except Exception as e:
        logger.error(f"❌ Error in generate_ai_response: {str(e)}")
        return f"I apologize, but I encountered an error while processing your request. Please try again. Error: {str(e)}"
        # If only 'web' is enabled, skip all model calls but provide comprehensive web results
        if set(active_tools) == {'web'}:
            try:
                logger.info(f"🌐 Web-only mode: Using advanced multi-engine search for: {message}")
                
                # Use the advanced search wrapper for comprehensive web-only results
                search_data = search_wrapper.enhanced_search_with_mining(message, deep_search=False)
                
                if search_data and search_data['results']:
                    # Build comprehensive web-only result
                    web_content_parts = []
                    
                    # Add summary
                    if search_data.get('summary'):
                        web_content_parts.append(f"📖 **Summary from {len(search_data['sources'])} Search Engines:**\n{search_data['summary']}")
                    
                    # Add key facts
                    if search_data.get('key_facts'):
                        web_content_parts.append(f"💡 **Key Facts Discovered:**")
                        for i, fact in enumerate(search_data['key_facts'][:7], 1):
                            web_content_parts.append(f"{i}. {fact}")
                    
                    # Add search results with source diversity
                    if search_data['results']:
                        web_content_parts.append(f"🔍 **Comprehensive Search Results:**")
                        web_content_parts.append(f"*Searched across: {', '.join(search_data['sources'])}")
                        
                        for i, result in enumerate(search_data['results'][:8], 1):
                            web_content_parts.append(f"**{i}. {result.title}** (via {result.source})")
                            if result.snippet:
                                web_content_parts.append(f"   {result.snippet}")
                            if result.url:
                                web_links.append({'title': result.title, 'url': result.url})
                    
                    # Add related topics for exploration
                    if search_data.get('related_topics'):
                        web_content_parts.append(f"🔗 **Related Topics to Explore:**")
                        for topic in search_data['related_topics'][:10]:
                            web_content_parts.append(f"• {topic}")
                    
                    # Add content snippets if available
                    content_results = [r for r in search_data['results'] if r.content]
                    if content_results:
                        web_content_parts.append(f"📄 **Content Previews:**")
                        for i, result in enumerate(content_results[:3], 1):
                            web_content_parts.append(f"**From {result.title}:**")
                            web_content_parts.append(f"{result.content[:300]}...")
                    
                    web_result = "🌐 **Advanced Multi-Engine Web Search:**\n\n" + "\n\n".join(web_content_parts)
                    
                    logger.info(f"✅ Web-only search: {len(search_data['results'])} results from {len(search_data['sources'])} engines")
                    
                else:
                    # Fallback if advanced search fails
                    logger.warning("Advanced search failed, using AI knowledge fallback")
                    if 'ai' in message.lower():
                        web_result = f"""🌐 **Latest AI Developments (2024-2025):**

**🚀 Major Breakthroughs:**
• **GPT-5 & Beyond** - OpenAI's next-generation models with enhanced reasoning
• **Gemini Advanced** - Google's multimodal AI with improved capabilities
• **Claude 3.5** - Anthropic's latest with better code understanding
• **Llama 3** - Meta's open-source model matching closed-source performance

**🔬 Technical Advances:**
• **Reasoning Models** - AI that can think step-by-step (like o1, R1)
• **Multimodal AI** - Models that understand text, images, audio, and video
• **Agentic AI** - AI that can take actions and use tools autonomously
• **Edge AI** - Running powerful models on local devices

**🏭 Industry Applications:**
• **Coding Assistants** - GitHub Copilot, Cursor, V0 for development
• **Video Generation** - Sora, Runway, Pika for content creation
• **Scientific Research** - AlphaFold 3 for protein structure prediction
• **Robotics** - Humanoid robots with AI integration

**🌍 Recent Trends:**
• **Open Source Movement** - More powerful models becoming freely available
• **AI Regulation** - EU AI Act and other governance frameworks
• **Cost Reduction** - AI becoming more accessible and affordable
• **Safety Research** - Focus on alignment and responsible AI development

The AI field is evolving rapidly with new models and applications emerging monthly!"""
                    else:
                        web_result = f"🌐 **Search Results for '{message}':**\nI searched multiple engines for current information. While some results may be limited, I can provide comprehensive information based on available knowledge. For the most current details, please try specific search terms or check recent news sources."
                        
            except Exception as e:
                logger.error(f"🌐 Advanced web search error: {str(e)}")
                web_result = f"🌐 **Web Search Error:** Unable to complete search across multiple engines. Error: {str(e)}"
            
            # Format final response with comprehensive links
            final_response = web_result or "🌐 **No Results:** Unable to find information about your query."
            if web_links:
                final_response += "\n\n📚 **Reference Links & Sources:**\n"
                for i, link in enumerate(web_links, 1):
                    final_response += f"{i}. **{link['title']}**\n   🔗 {link['url']}\n"
            
            return final_response.strip()
        # Otherwise, use normal model selection logic
        models_to_try = set()
        if not active_tools:
            # If no tools are selected, use default models (GPT-4o and GPT-4.1)
            logger.info("📝 No tools selected, using default models (GPT-4o, GPT-4.1)")
            models_to_try.update(model_groups['default'])
        else:
            if 'think' in active_tools:
                logger.info("🧠 Think mode enabled - using DeepSeek R1 models")
                models_to_try.update(model_groups['think'])
            if 'deepsearch' in active_tools or 'research' in active_tools:
                logger.info("🔍 Deep Search mode enabled - using Perplexity + Gemini + Web Search")
                models_to_try.update(model_groups['deepsearch'])
            if 'code' in active_tools:
                logger.info("💻 Code mode enabled - using Qwen3 Coder + Gemma 3n")
                models_to_try.update(model_groups['code'])
            if not models_to_try and 'web' not in active_tools:
                # If only unknown tools are selected and no web, fall back to default
                logger.info("⚠️ Unknown tools selected, falling back to default models")
                models_to_try.update(model_groups['default'])
        # Enhanced web search for 'web' tool or 'deepsearch' mode
        if 'web' in active_tools or 'deepsearch' in active_tools or 'research' in active_tools:
            try:
                logger.info(f"🔍 Using advanced multi-engine search for: {message}")
                
                # Use the advanced search wrapper for comprehensive results
                search_data = search_wrapper.enhanced_search_with_mining(
                    message, 
                    deep_search=('deepsearch' in active_tools or 'research' in active_tools)
                )
                
                if search_data and search_data['results']:
                    # Build comprehensive web result from multiple engines
                    web_parts = []
                    
                    # Add summary if available
                    if search_data.get('summary'):
                        web_parts.append(f"📖 **Comprehensive Summary:**\n{search_data['summary']}")
                    
                    # Add key facts
                    if search_data.get('key_facts'):
                        web_parts.append(f"💡 **Key Facts:**")
                        for i, fact in enumerate(search_data['key_facts'][:5], 1):
                            web_parts.append(f"{i}. {fact}")
                    
                    # Add top search results
                    if search_data['results']:
                        web_parts.append(f"� **Search Results from {len(search_data['sources'])} engines:**")
                        for i, result in enumerate(search_data['results'][:5], 1):
                            web_parts.append(f"**{i}. {result.title}** ({result.source})")
                            if result.snippet:
                                web_parts.append(f"   {result.snippet}")
                            if result.url:
                                web_links.append({'title': result.title, 'url': result.url})
                    
                    # Add scraped content for deep search
                    if 'deepsearch' in active_tools or 'research' in active_tools:
                        content_results = [r for r in search_data['results'] if r.content]
                        if content_results:
                            web_parts.append(f"📄 **Detailed Content Analysis:**")
                            for i, result in enumerate(content_results[:3], 1):
                                web_parts.append(f"**{i}. From {result.title}:**")
                                web_parts.append(f"{result.content[:400]}...")
                    
                    # Add related topics
                    if search_data.get('related_topics'):
                        web_parts.append(f"🔗 **Related Topics:**")
                        for topic in search_data['related_topics'][:8]:
                            web_parts.append(f"• {topic}")
                    
                    web_result = "🌐 **Advanced Multi-Engine Search Results:**\n\n" + "\n\n".join(web_parts)
                    
                    logger.info(f"✅ Advanced search complete: {len(search_data['results'])} results from {len(search_data['sources'])} engines")
                    
                else:
                    logger.warning("No results from advanced search, falling back to knowledge base")
                    web_result = None
                    
            except Exception as e:
                logger.error(f"🌐 Advanced search error: {str(e)}")
                # Fallback to simple DuckDuckGo search
                try:
                    ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(message)}&format=json&no_redirect=1&no_html=1"
                    headers = {'User-Agent': 'Companion-AI/1.0 (Educational Research Bot)'}
                    web_resp = pyrequests.get(ddg_url, headers=headers, timeout=10)
                    
                    if web_resp.status_code in [200, 202]:
                        web_json = web_resp.json()
                        abstract = web_json.get('AbstractText', '')
                        if abstract:
                            web_result = f"🌐 **Search Results:**\n\n📖 **Summary:** {abstract}"
                            if web_json.get('AbstractURL'):
                                web_links.append({'title': web_json.get('AbstractSource', 'Source'), 'url': web_json.get('AbstractURL')})
                        else:
                            web_result = None
                    else:
                        web_result = None
                except Exception as fallback_error:
                    logger.error(f"Fallback search also failed: {fallback_error}")
                    web_result = None
        for model_name in models_to_try:
            try:
                if chat_history is None:
                    chat_history = []
                model_config = get_model_config(model_name)
                if not model_config:
                    logger.warning(f"Model {model_name} not configured, trying next...")
                    continue
                headers = get_openrouter_headers(model_name)
                logger.info(f"Trying model {model_name}")
                system_prompt = """You are Companion, a helpful AI assistant. You provide clear, accurate, and engaging responses. \nYou can help with programming, general knowledge, explanations, creative writing, problem-solving, and more.\nBe concise but informative in your responses."""
                messages = [{"role": "system", "content": system_prompt}]
                if chat_history:
                    recent_history = chat_history[-4:] if len(chat_history) > 4 else chat_history
                    messages.extend(recent_history)
                messages.append({"role": "user", "content": message})
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "stream": False,
                    "temperature": 0.7,
                    "max_tokens": 1500,
                    "top_p": 0.9,
                }
                response = pyrequests.post(
                    f"{OPENROUTER_CONFIG['base_url']}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=15
                )
                if response.status_code == 200:
                    response_data = response.json()
                    if 'choices' in response_data and len(response_data['choices']) > 0:
                        ai_response = response_data['choices'][0]['message']['content']
                        logger.info(f"✅ Successfully got response from {model_name}")
                        
                        # Check if this is a thinking model (DeepSeek R1) and extract thinking data
                        thinking_data = None
                        if 'deepseek' in model_name.lower() and 'r1' in model_name.lower():
                            thinking_data = extract_thinking_data(ai_response)
                            logger.info(f"🧠 Extracted thinking data: {len(thinking_data) if thinking_data else 0} characters")
                            if thinking_data:
                                # Store thinking data for later use
                                responses.append({
                                    'model': model_name.split('/')[-1],
                                    'content': ai_response.strip(),
                                    'thinking': thinking_data
                                })
                            else:
                                responses.append(f"[{model_name.split('/')[-1]}]: {ai_response.strip()}")
                        else:
                            responses.append(f"[{model_name.split('/')[-1]}]: {ai_response.strip()}")
                    else:
                        logger.error(f"No choices in response from {model_name}: {response_data}")
                        continue
                elif response.status_code == 401:
                    logger.warning(f"❌ Auth error for {model_name}, trying next model...")
                    continue
                else:
                    logger.warning(f"⚠️ API error for {model_name}: {response.status_code}, trying next...")
                    continue
            except pyrequests.exceptions.Timeout:
                logger.warning(f"⏰ Timeout for model {model_name}, trying next...")
                continue
            except pyrequests.exceptions.RequestException as e:
                logger.warning(f"🌐 Request failed for {model_name}: {str(e)}, trying next...")
                continue
            except Exception as e:
                logger.warning(f"💥 Unexpected error for {model_name}: {str(e)}, trying next...")
                continue
        final_response = ""
        thinking_data = None
        
        # Check if any responses contain thinking data
        for response in responses:
            if isinstance(response, dict) and response.get('thinking'):
                thinking_data = response['thinking']
                break
        
        # Format response based on active tools
        if 'deepsearch' in active_tools or 'research' in active_tools:
            # For deep search, integrate web results with AI analysis
            if web_result:
                final_response += web_result + "\n\n"
            if responses:
                formatted_responses = []
                for resp in responses:
                    if isinstance(resp, dict):
                        formatted_responses.append(f"[{resp['model']}]: {resp['content']}")
                    else:
                        formatted_responses.append(resp)
                final_response += "🤖 **AI Analysis & Synthesis:**\n\n" + "\n\n".join(formatted_responses)
            if web_links:
                final_response += "\n\n📚 **Comprehensive Sources & References:**\n"
                for i, link in enumerate(web_links, 1):
                    final_response += f"{i}. **{link['title']}**\n   🔗 {link['url']}\n"
        elif set(active_tools) == {'web'}:
            # Web-only mode already handled above
            pass
        else:
            # Default mode: web first (if available), then AI responses
            if web_result:
                final_response += web_result + "\n\n"
            if responses:
                formatted_responses = []
                for resp in responses:
                    if isinstance(resp, dict):
                        formatted_responses.append(f"[{resp['model']}]: {resp['content']}")
                    else:
                        formatted_responses.append(resp)
                final_response += "\n\n".join(formatted_responses)
            if web_links:
                final_response += "\n\n� **Reference Links & Additional Reading:**\n"
                for i, link in enumerate(web_links, 1):
                    final_response += f"{i}. **{link['title']}**\n   🔗 {link['url']}\n"
        # If web_result exists but no model responses, return web_result only
        if web_result and not responses:
            if thinking_data:
                return {"content": final_response.strip(), "thinking": thinking_data}
            else:
                return final_response.strip()
        if not final_response:
            logger.error("🔥 All API models and web search failed")
            return "I'm having trouble connecting to the AI services and web search right now. Please try again later."
        
        # Return with thinking data if available
        if thinking_data:
            final_result = {"content": final_response, "thinking": thinking_data}
        else:
            final_result = final_response
        
        # Apply reinforcement learning and NLP-enhanced feedback
        if final_response and len(final_response) > 50:
            # Use reinforcement learning update instead of simple adaptive learning
            threading.Thread(target=reinforcement_learning_update, args=(message, final_response), daemon=True).start()
            
            # Enhance response with NLP insights
            final_response = intelligent_response_enhancement(message, final_response)
        
        # Enhance with cached knowledge if available
        cache_enhancement = enhanced_response_with_cache(message)
        if cache_enhancement and not web_result:  # Only add if no web search was performed
            if isinstance(final_response, dict):
                final_response["content"] = cache_enhancement + "\n\n" + final_response["content"]
            else:
                final_response = cache_enhancement + "\n\n" + final_response
        
        return final_result
    except Exception as e:
        logger.error(f"Critical error in AI response generation: {str(e)}")
        return "I encountered an unexpected error. Please try again."

def generate_intelligent_fallback_response(message, chat_history=None):
    """Generate intelligent responses when API is unavailable"""
    message_lower = message.lower()
    
    # Handle ambiguous name queries with enhanced context
    if any(pattern in message_lower for pattern in ['who is aryan', 'about aryan', 'tell me about aryan']):
        return """🤔 **About "Aryan" - Multiple Meanings & Contexts:**

**📚 Historical & Linguistic Context:**
The term "Aryan" has multiple meanings, historically and currently:

**1. 🏛️ Linguistic & Historical Context:**
• **Indo-Iranians:** Originally referred to Indo-Iranian peoples who spoke languages that branched into Indo-Aryan and Iranian languages
• **Sanskrit Origin:** Derived from Sanskrit "Arya" meaning "noble" or "honorable"  
• **Vedic Period:** Used by ancient Indo-Aryan peoples in India to refer to themselves and their culture
• **Migration Patterns:** These migrations brought Indo-Aryan languages and cultural practices into South Asia

**2. ⚠️ Historical Misappropriation:**
• **19th Century Misuse:** The term was incorrectly adopted by some European thinkers to describe a supposed "superior white race"
• **Nazi Ideology:** Misused by Nazi Germany as basis for racist policies and genocide
• **Modern Context:** Still misused by some supremacist groups despite being thoroughly discredited

**3. 👤 As a Personal Name:**
• **Common Name:** Widely used, particularly in Indian and Middle Eastern cultures
• **Meaning:** Often chosen for its positive connotations of nobility and honor
• **Modern Usage:** Many notable people across various fields share this name

**🔍 For More Specific Information:**
• Try adding context: "Aryan [profession]", "Aryan [location]", or "Aryan [last name]"
• Use the **Web Search** or **Research** tools for specific individuals
• Include additional identifying details for better search results

**💡 Pro Tip:** The context matters greatly - be specific about which "Aryan" you're asking about for more accurate results!

*If you're looking for information about a specific person named Aryan, please provide additional context like their profession, achievements, or other identifying details.*"""
    
    # Programming and technical responses
    elif 'calculator' in message_lower:
        
        # HTML Calculator
        if any(word in message_lower for word in ['html', 'web', 'webpage']):
            return '''Here's a simple HTML calculator:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Simple Calculator</title>
    <style>
        .calculator {
            max-width: 300px;
            margin: 50px auto;
            border: 1px solid #ccc;
            border-radius: 10px;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .display {
            width: 100%;
            height: 50px;
            font-size: 24px;
            text-align: right;
            margin-bottom: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 0 10px;
        }
        .buttons {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
        }
        button {
            height: 50px;
            font-size: 18px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        .number { background-color: #e0e0e0; }
        .operator { background-color: #ff9500; color: white; }
        .equals { background-color: #ff9500; color: white; }
        .clear { background-color: #ff6b6b; color: white; }
    </style>
</head>
<body>
    <div class="calculator">
        <input type="text" class="display" id="display" readonly>
        <div class="buttons">
            <button class="clear" onclick="clearDisplay()">C</button>
            <button class="operator" onclick="deleteLast()">⌫</button>
            <button class="operator" onclick="appendToDisplay('/')">/</button>
            <button class="operator" onclick="appendToDisplay('*')">×</button>
            
            <button class="number" onclick="appendToDisplay('7')">7</button>
            <button class="number" onclick="appendToDisplay('8')">8</button>
            <button class="number" onclick="appendToDisplay('9')">9</button>
            <button class="operator" onclick="appendToDisplay('-')">-</button>
            
            <button class="number" onclick="appendToDisplay('4')">4</button>
            <button class="number" onclick="appendToDisplay('5')">5</button>
            <button class="number" onclick="appendToDisplay('6')">6</button>
            <button class="operator" onclick="appendToDisplay('+')">+</button>
            
            <button class="number" onclick="appendToDisplay('1')">1</button>
            <button class="number" onclick="appendToDisplay('2')">2</button>
            <button class="number" onclick="appendToDisplay('3')">3</button>
            <button class="equals" onclick="calculate()" style="grid-row: span 2;">=</button>
            
            <button class="number" onclick="appendToDisplay('0')" style="grid-column: span 2;">0</button>
            <button class="number" onclick="appendToDisplay('.')">.</button>
        </div>
    </div>

    <script>
        function appendToDisplay(value) {
            document.getElementById('display').value += value;
        }
        
        function clearDisplay() {
            document.getElementById('display').value = '';
        }
        
        function deleteLast() {
            let display = document.getElementById('display');
            display.value = display.value.slice(0, -1);
        }
        
        function calculate() {
            try {
                let result = eval(document.getElementById('display').value);
                document.getElementById('display').value = result;
            } catch (error) {
                document.getElementById('display').value = 'Error';
            }
        }
    </script>
</body>
</html>
```

This creates a fully functional calculator with a clean, modern interface!'''

        # C Calculator
        elif any(word in message_lower for word in [' c ', 'c language', 'c code', 'c programming']):
            return '''Here's a simple C calculator:

```c
#include <stdio.h>
#include <stdlib.h>

double calculate(double num1, double num2, char operation) {
    switch(operation) {
        case '+': return num1 + num2;
        case '-': return num1 - num2;
        case '*': return num1 * num2;
        case '/': 
            if(num2 == 0) {
                printf("Error: Division by zero!\\n");
                return 0;
            }
            return num1 / num2;
        default:
            printf("Error: Invalid operation!\\n");
            return 0;
    }
}

int main() {
    double num1, num2, result;
    char operation, choice;
    
    printf("Simple Calculator\\n");
    printf("Operations: +, -, *, /\\n\\n");
    
    do {
        printf("Enter first number: ");
        if(scanf("%lf", &num1) != 1) {
            printf("Error: Invalid input!\\n");
            while(getchar() != '\\n'); // Clear input buffer
            continue;
        }
        
        printf("Enter operation (+, -, *, /): ");
        scanf(" %c", &operation);
        
        printf("Enter second number: ");
        if(scanf("%lf", &num2) != 1) {
            printf("Error: Invalid input!\\n");
            while(getchar() != '\\n'); // Clear input buffer
            continue;
        }
        
        result = calculate(num1, num2, operation);
        printf("Result: %.2f %c %.2f = %.2f\\n\\n", num1, operation, num2, result);
        
        printf("Continue? (y/n): ");
        scanf(" %c", &choice);
        
    } while(choice == 'y' || choice == 'Y');
    
    printf("Calculator closed. Goodbye!\\n");
    return 0;
}
```

This C calculator includes proper error handling and input validation!'''

        # C++ Calculator
        elif any(word in message_lower for word in ['c++', 'cpp', 'c plus']):
            return '''Here's a simple C++ calculator:

```cpp
#include <iostream>
#include <iomanip>
#include <limits>

class Calculator {
private:
    double num1, num2;
    char operation;
    
public:
    void getInput() {
        std::cout << "Enter first number: ";
        while(!(std::cin >> num1)) {
            std::cout << "Error: Please enter a valid number: ";
            std::cin.clear();
            std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\\n');
        }
        
        std::cout << "Enter operation (+, -, *, /): ";
        std::cin >> operation;
        
        std::cout << "Enter second number: ";
        while(!(std::cin >> num2)) {
            std::cout << "Error: Please enter a valid number: ";
            std::cin.clear();
            std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\\n');
        }
    }
    
    double calculate() {
        switch(operation) {
            case '+': return num1 + num2;
            case '-': return num1 - num2;
            case '*': return num1 * num2;
            case '/':
                if(num2 == 0) {
                    throw std::runtime_error("Division by zero!");
                }
                return num1 / num2;
            default:
                throw std::invalid_argument("Invalid operation!");
        }
    }
    
    void displayResult() {
        try {
            double result = calculate();
            std::cout << std::fixed << std::setprecision(2);
            std::cout << "Result: " << num1 << " " << operation << " " 
                      << num2 << " = " << result << std::endl << std::endl;
        } catch(const std::exception& e) {
            std::cout << "Error: " << e.what() << std::endl << std::endl;
        }
    }
};

int main() {
    Calculator calc;
    char choice;
    
    std::cout << "Simple C++ Calculator" << std::endl;
    std::cout << "Operations: +, -, *, /" << std::endl << std::endl;
    
    do {
        calc.getInput();
        calc.displayResult();
        
        std::cout << "Continue? (y/n): ";
        std::cin >> choice;
        std::cout << std::endl;
        
    } while(choice == 'y' || choice == 'Y');
    
    std::cout << "Calculator closed. Goodbye!" << std::endl;
    return 0;
}
```

This C++ calculator uses object-oriented programming with proper exception handling!'''

        # Java Calculator
        elif 'java' in message_lower:
            return '''Here's a simple Java calculator:

```java
import java.util.Scanner;

public class SimpleCalculator {
    private static Scanner scanner = new Scanner(System.in);
    
    public static void main(String[] args) {
        System.out.println("Simple Calculator");
        System.out.println("Operations: +, -, *, /");
        
        while (true) {
            try {
                System.out.print("Enter first number: ");
                double num1 = scanner.nextDouble();
                
                System.out.print("Enter operation (+, -, *, /): ");
                char operation = scanner.next().charAt(0);
                
                System.out.print("Enter second number: ");
                double num2 = scanner.nextDouble();
                
                double result = 0;
                boolean validOperation = true;
                
                switch(operation) {
                    case '+': result = num1 + num2; break;
                    case '-': result = num1 - num2; break;
                    case '*': result = num1 * num2; break;
                    case '/':
                        if(num2 == 0) {
                            System.out.println("Error: Division by zero!");
                            validOperation = false;
                        } else {
                            result = num1 / num2;
                        }
                        break;
                    default:
                        System.out.println("Error: Invalid operation!");
                        validOperation = false;
                }
                
                if(validOperation) {
                    System.out.printf("Result: %.2f %c %.2f = %.2f%n%n", 
                                    num1, operation, num2, result);
                }
                
                System.out.print("Continue? (y/n): ");
                String choice = scanner.next();
                if(!choice.equalsIgnoreCase("y")) {
                    break;
                }
                
            } catch(Exception e) {
                System.out.println("Error: Please enter valid numbers!");
                scanner.nextLine(); // Clear the buffer
            }
        }
        
        System.out.println("Calculator closed. Goodbye!");
        scanner.close();
    }
}
```

This Java calculator includes proper error handling and a clean interface!'''

        # Python Calculator
        elif 'python' in message_lower or 'py' in message_lower:
            return '''Here's a simple Python calculator:

```python
def calculator():
    print("Simple Calculator")
    while True:
        try:
            num1 = float(input("Enter first number: "))
            operation = input("Enter operation (+, -, *, /): ")
            num2 = float(input("Enter second number: "))
            
            if operation == '+':
                result = num1 + num2
            elif operation == '-':
                result = num1 - num2
            elif operation == '*':
                result = num1 * num2
            elif operation == '/':
                result = num1 / num2 if num2 != 0 else "Error: Division by zero"
            else:
                print("Invalid operation!")
                continue
                
            print(f"Result: {num1} {operation} {num2} = {result}")
            
            if input("Continue? (y/n): ").lower() != 'y':
                break
        except ValueError:
            print("Please enter valid numbers!")

calculator()
```

This Python calculator includes error handling and a clean interface!'''
        
        # General calculator (default when language is unspecified)
        else:
            return '''Here's a simple calculator. Which programming language would you prefer?

**Python Calculator:**
```python
def calculator():
    print("Simple Calculator")
    while True:
        try:
            num1 = float(input("Enter first number: "))
            operation = input("Enter operation (+, -, *, /): ")
            num2 = float(input("Enter second number: "))
            
            if operation == '+':
                result = num1 + num2
            elif operation == '-':
                result = num1 - num2
            elif operation == '*':
                result = num1 * num2
            elif operation == '/':
                result = num1 / num2 if num2 != 0 else "Error: Division by zero"
            else:
                print("Invalid operation!")
                continue
                
            print(f"Result: {num1} {operation} {num2} = {result}")
            
            if input("Continue? (y/n): ").lower() != 'y':
                break
        except ValueError:
            print("Please enter valid numbers!")

calculator()
```

You can also ask me for calculators in **HTML**, **C**, **C++**, or **Java** by specifying the language in your request!'''
    
    # Programming questions (non-calculator)
    elif any(word in message_lower for word in ['code', 'programming', 'function', 'script']):
        return '''I can help you with programming! I support many languages including:

**Popular Languages:**
• Python - Great for beginners, data science, web development
• JavaScript - Web development, both frontend and backend
• Java - Enterprise applications, Android development
• C/C++ - System programming, game development
• HTML/CSS - Web structure and styling
• SQL - Database queries and management

**What I can help with:**
• Code examples and templates
• Debugging and troubleshooting
• Best practices and optimization
• Algorithm explanations
• Project structure and design patterns

What specific programming topic or language would you like to explore?'''
    
    # General knowledge and explanations
    elif any(word in message_lower for word in ['quantum', 'computing', 'physics']):
        return '''Quantum computing is a revolutionary technology that uses quantum mechanical phenomena to process information in ways that classical computers cannot.

**Key Concepts:**

🔬 **Qubits** - Unlike classical bits (0 or 1), qubits can exist in "superposition" - being both 0 and 1 simultaneously until measured.

🔗 **Entanglement** - Qubits can be "entangled," meaning their states become correlated even when separated by large distances.

⚡ **Quantum Interference** - Quantum algorithms use interference to amplify correct answers and cancel out wrong ones.

**Potential Applications:**
• Cryptography and security
• Drug discovery and molecular modeling
• Financial modeling and optimization
• Machine learning and AI
• Weather prediction and climate modeling

**Current Challenges:**
• Quantum decoherence (qubits are very fragile)
• Error correction requirements
• Limited number of stable qubits
• Extremely cold operating temperatures needed

While still in early stages, quantum computers could solve certain problems exponentially faster than classical computers. Companies like IBM, Google, and others are making significant progress!

Would you like me to explain any specific aspect in more detail?'''
    
    # Greetings and general conversation
    elif any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings']):
        return f'''Hello! 👋 I'm Companion, your AI assistant. I'm here to help you with a wide variety of tasks and questions.

**I can help you with:**
• Programming and code development
• General knowledge and explanations
• Creative writing and brainstorming
• Problem-solving and analysis
• Learning new concepts
• And much more!

**Current Status:** I'm running in smart fallback mode while the advanced AI models are being configured. I can still provide helpful responses and code examples!

What would you like to explore or work on today?'''
    
    # Math and calculations
    elif any(word in message_lower for word in ['math', 'calculate', 'equation', 'formula']):
        return '''I'd be happy to help with math! I can assist with:

**Areas of Mathematics:**
• Basic arithmetic and algebra
• Geometry and trigonometry
• Calculus and derivatives
• Statistics and probability
• Linear algebra and matrices
• Number theory and discrete math

**What I can do:**
• Solve equations step by step
• Explain mathematical concepts
• Provide formulas and examples
• Help with word problems
• Create visual representations in code

**Example:** If you're working on calculus, I can help find derivatives:
- The derivative of f(x) = x² is f'(x) = 2x
- Using the power rule: d/dx(xⁿ) = n·xⁿ⁻¹

What specific math topic or problem would you like help with?'''
    
    # Default intelligent response
    else:
        return f'''I understand you're asking about: "{message}"

**I'm Companion, your AI assistant!** While I'm currently in fallback mode, I can still help with:

📚 **Learning & Explanation**
• Breaking down complex topics
• Step-by-step tutorials
• Concept clarification

💻 **Programming & Tech**
• Code examples in multiple languages
• Debugging assistance
• Best practices and patterns

🧠 **Problem Solving**
• Analytical thinking
• Creative solutions
• Research guidance

✍️ **Writing & Communication**
• Content creation
• Editing and improvement
• Structured thinking

**For your question about "{message}":** Could you provide a bit more context or specify what aspect you'd like me to focus on? This helps me give you the most relevant and useful response.

The desktop version of Companion has access to more advanced AI capabilities for even better assistance!'''
    
    return response

def extract_question_pattern(message):
    """Extract a pattern from user message for learning"""
    import re
    
    # Clean and normalize the message
    message_clean = re.sub(r'[^\w\s]', '', message.lower())
    
    # Extract key terms (3+ character words)
    words = [word for word in message_clean.split() if len(word) >= 3]
    
    # Take up to 5 most relevant words
    pattern_words = words[:5]
    return ' '.join(pattern_words)

def save_successful_response(question, response, feedback_score=5.0):
    """Save a successful response for future learning"""
    try:
        pattern = extract_question_pattern(question)
        if not pattern:
            return
        
        conn = get_db_connection()
        
        # Check if pattern already exists
        existing = conn.execute('''
            SELECT id, usage_count, feedback_score FROM learning_data 
            WHERE question_pattern = ?
        ''', (pattern,)).fetchone()
        
        if existing:
            # Update existing pattern with better score or increased usage
            new_usage = existing['usage_count'] + 1
            new_score = (existing['feedback_score'] + feedback_score) / 2  # Average the scores
            
            conn.execute('''
                UPDATE learning_data 
                SET usage_count = ?, feedback_score = ?, last_used = CURRENT_TIMESTAMP,
                    successful_response = ?
                WHERE id = ?
            ''', (new_usage, new_score, response[:1000], existing['id']))
        else:
            # Create new learning entry
            learning_id = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO learning_data 
                (id, question_pattern, successful_response, feedback_score, usage_count)
                VALUES (?, ?, ?, ?, 1)
            ''', (learning_id, pattern, response[:1000], feedback_score))
        
        conn.commit()
        conn.close()
        
        logger.info(f"🧠 Learned pattern: {pattern} (score: {feedback_score})")
        
    except Exception as e:
        logger.error(f"Error saving learning data: {e}")

def find_learned_response(message):
    """Find a learned response for similar questions"""
    try:
        pattern = extract_question_pattern(message)
        if not pattern:
            return None
        
        conn = get_db_connection()
        
        # First try exact pattern match
        exact_match = conn.execute('''
            SELECT successful_response, feedback_score, usage_count 
            FROM learning_data 
            WHERE question_pattern = ? AND feedback_score >= 4.0
            ORDER BY usage_count DESC, feedback_score DESC
            LIMIT 1
        ''', (pattern,)).fetchone()
        
        if exact_match:
            # Update usage count
            conn.execute('''
                UPDATE learning_data 
                SET usage_count = usage_count + 1, last_used = CURRENT_TIMESTAMP
                WHERE question_pattern = ?
            ''', (pattern,))
            conn.commit()
            conn.close()
            
            logger.info(f"🎯 Found exact learned response for: {pattern}")
            return f"🧠 **Based on previous successful interactions:**\n\n{exact_match['successful_response']}"
        
        # Try partial matches for similar patterns
        pattern_words = pattern.split()
        if len(pattern_words) >= 2:
            partial_patterns = []
            for i in range(len(pattern_words)):
                for j in range(i + 2, len(pattern_words) + 1):
                    partial_patterns.append(' '.join(pattern_words[i:j]))
            
            for partial in partial_patterns:
                if len(partial) >= 6:  # Minimum length for meaningful partial match
                    partial_match = conn.execute('''
                        SELECT successful_response, feedback_score, usage_count 
                        FROM learning_data 
                        WHERE question_pattern LIKE ? AND feedback_score >= 4.0
                        ORDER BY usage_count DESC, feedback_score DESC
                        LIMIT 1
                    ''', (f'%{partial}%',)).fetchone()
                    
                    if partial_match:
                        conn.close()
                        logger.info(f"🎯 Found partial learned response for: {partial}")
                        return f"🧠 **Similar to previous questions:**\n\n{partial_match['successful_response']}"
        
        conn.close()
        return None
        
    except Exception as e:
        logger.error(f"Error finding learned response: {e}")
        return None

def extract_learning_patterns(message):
    """Extract learning patterns from user messages for personalization"""
    try:
        patterns = []
        message_lower = message.lower()
        
        # Detect question types
        if any(word in message_lower for word in ['how', 'what', 'why', 'when', 'where', 'which']):
            patterns.append('question_based')
        
        if any(word in message_lower for word in ['code', 'program', 'function', 'script', 'debug']):
            patterns.append('programming_related')
        
        if any(word in message_lower for word in ['explain', 'understand', 'learn', 'teach']):
            patterns.append('educational')
        
        if any(word in message_lower for word in ['help', 'assist', 'support', 'guide']):
            patterns.append('assistance_seeking')
        
        if any(word in message_lower for word in ['create', 'make', 'build', 'generate']):
            patterns.append('creative_request')
        
        # Detect complexity level
        word_count = len(message.split())
        if word_count > 20:
            patterns.append('complex_query')
        elif word_count > 10:
            patterns.append('medium_query')
        else:
            patterns.append('simple_query')
        
        # Detect technical level
        technical_words = ['api', 'database', 'algorithm', 'framework', 'library', 'server', 'client']
        if any(word in message_lower for word in technical_words):
            patterns.append('technical')
        
        return patterns
        
    except Exception as e:
        logger.error(f"Error extracting learning patterns: {e}")
        return []

def adaptive_learning_feedback(message, response, user_rating=None):
    """Process user feedback for adaptive learning"""
    try:
        if user_rating is None:
            # Auto-assess response quality based on length and completeness
            if len(response) > 100 and not any(error in response.lower() for error in ['error', 'sorry', 'unable', 'cannot']):
                user_rating = 4.5
            else:
                user_rating = 3.0
        
        # Save the interaction for learning
        save_successful_response(message, response, user_rating)
        
        # Extract and save learning patterns
        patterns = extract_learning_patterns(message)
        
        # Store patterns for future use (simplified implementation)
        conn = get_db_connection()
        try:
            pattern_data = {
                'message': message[:200],
                'patterns': patterns,
                'rating': user_rating,
                'timestamp': datetime.now().isoformat()
            }
            
            # Store in a simple way (you could expand this to a separate table)
            logger.info(f"📈 Learning patterns: {patterns} (rating: {user_rating})")
            
        except Exception as e:
            logger.warning(f"Error storing learning patterns: {e}")
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error in adaptive learning feedback: {e}")

# ===== NLP and Advanced Learning Functions =====

def analyze_message_sentiment(message):
    """Analyze sentiment and emotional tone of user message using NLP"""
    if not NLP_AVAILABLE:
        return {'sentiment': 'neutral', 'polarity': 0.0, 'subjectivity': 0.5}
    
    try:
        blob = TextBlob(message)
        polarity = blob.sentiment.polarity  # -1 (negative) to 1 (positive)
        subjectivity = blob.sentiment.subjectivity  # 0 (objective) to 1 (subjective)
        
        # Classify sentiment
        if polarity > 0.1:
            sentiment = 'positive'
        elif polarity < -0.1:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        return {
            'sentiment': sentiment,
            'polarity': polarity,
            'subjectivity': subjectivity,
            'confidence': abs(polarity)
        }
    except Exception as e:
        logger.warning(f"Error analyzing sentiment: {e}")
        return {'sentiment': 'neutral', 'polarity': 0.0, 'subjectivity': 0.5}

def extract_key_entities(message):
    """Extract key entities and topics from user message"""
    if not NLP_AVAILABLE:
        return {'entities': [], 'pos_tags': [], 'keywords': []}
    
    try:
        blob = TextBlob(message)
        
        # Get POS tags
        pos_tags = [(word, tag) for word, tag in blob.tags if tag in ['NN', 'NNP', 'NNS', 'NNPS', 'VB', 'VBG', 'VBN', 'VBP', 'VBZ']]
        
        # Extract potential entities (proper nouns and significant words)
        entities = [word for word, tag in blob.tags if tag in ['NNP', 'NNPS']]
        
        # Extract keywords (nouns and verbs, filtered by length)
        keywords = [word.lower() for word, tag in blob.tags 
                   if tag in ['NN', 'NNS', 'VB', 'VBG', 'VBN'] and len(word) > 3]
        
        return {
            'entities': entities[:10],  # Top 10 entities
            'pos_tags': pos_tags[:15],  # Top 15 POS tags
            'keywords': list(set(keywords))[:10]  # Top 10 unique keywords
        }
    except Exception as e:
        logger.warning(f"Error extracting entities: {e}")
        return {'entities': [], 'pos_tags': [], 'keywords': []}

def semantic_similarity_search(query, stored_patterns, threshold=0.3):
    """Find semantically similar questions using TF-IDF vectorization"""
    if not NLP_AVAILABLE or not stored_patterns:
        return []
    
    try:
        # Create corpus including the query
        corpus = [query] + [pattern['question'] for pattern in stored_patterns]
        
        # Vectorize using TF-IDF
        vectorizer = TfidfVectorizer(
            stop_words='english',
            lowercase=True,
            ngram_range=(1, 2),
            min_df=1,
            max_features=1000
        )
        
        tfidf_matrix = vectorizer.fit_transform(corpus)
        
        # Calculate similarities
        query_vector = tfidf_matrix[0:1]
        similarities = cosine_similarity(query_vector, tfidf_matrix[1:]).flatten()
        
        # Find similar patterns above threshold
        similar_patterns = []
        for i, similarity in enumerate(similarities):
            if similarity > threshold:
                similar_patterns.append({
                    'pattern': stored_patterns[i],
                    'similarity': float(similarity),
                    'question': stored_patterns[i]['question'],
                    'response': stored_patterns[i]['response']
                })
        
        # Sort by similarity
        similar_patterns.sort(key=lambda x: x['similarity'], reverse=True)
        return similar_patterns[:5]  # Return top 5 similar patterns
        
    except Exception as e:
        logger.warning(f"Error in semantic similarity search: {e}")
        return []

def reinforcement_learning_update(message, response, user_feedback=None, context_data=None):
    """Update learning model based on user feedback and interaction success"""
    try:
        # Analyze message properties
        sentiment_data = analyze_message_sentiment(message)
        entities_data = extract_key_entities(message)
        
        # Calculate interaction success score
        success_score = 0.5  # Default neutral score
        
        if user_feedback:
            if user_feedback == 'like' or user_feedback == 'positive':
                success_score = 0.9
            elif user_feedback == 'dislike' or user_feedback == 'negative':
                success_score = 0.1
        else:
            # Auto-assess based on response quality and context
            if len(response) > 100 and not any(error in response.lower() for error in ['error', 'sorry', 'unable']):
                success_score = 0.7
            
            # Boost score for comprehensive responses
            if len(response) > 500 and ('**' in response or '•' in response):
                success_score = min(0.9, success_score + 0.2)
        
        # Store reinforcement learning data
        conn = get_db_connection()
        rl_id = str(uuid.uuid4())
        
        # Create reinforcement learning entry
        conn.execute('''
            INSERT OR REPLACE INTO learning_data 
            (id, question_pattern, successful_response, feedback_score, usage_count)
            VALUES (?, ?, ?, ?, 1)
        ''', (rl_id, extract_question_pattern(message), response[:1000], success_score))
        
        # Update existing patterns with similar semantic meaning
        similar_patterns = []
        existing_patterns = conn.execute('''
            SELECT question_pattern, successful_response FROM learning_data 
            WHERE feedback_score >= 0.6
        ''').fetchall()
        
        if existing_patterns:
            pattern_list = [{'question': p['question_pattern'], 'response': p['successful_response']} 
                          for p in existing_patterns]
            similar_patterns = semantic_similarity_search(message, pattern_list, threshold=0.4)
        
        # Boost scores for semantically similar successful patterns
        for similar in similar_patterns:
            conn.execute('''
                UPDATE learning_data 
                SET feedback_score = feedback_score * 1.1, usage_count = usage_count + 1
                WHERE question_pattern = ? AND feedback_score < 1.0
            ''', (similar['pattern']['question'],))
        
        conn.commit()
        conn.close()
        
        logger.info(f"🤖 RL Update: Score {success_score}, Sentiment: {sentiment_data['sentiment']}, Similar patterns: {len(similar_patterns)}")
        
        return {
            'success_score': success_score,
            'sentiment': sentiment_data,
            'entities': entities_data,
            'similar_patterns_count': len(similar_patterns)
        }
        
    except Exception as e:
        logger.error(f"Error in reinforcement learning update: {e}")
        return None

def intelligent_response_enhancement(message, base_response):
    """Enhance response based on NLP analysis and learned patterns"""
    try:
        if not NLP_AVAILABLE:
            return base_response
        
        # Analyze user message
        sentiment_data = analyze_message_sentiment(message)
        entities_data = extract_key_entities(message)
        
        # Find similar successful interactions
        conn = get_db_connection()
        learned_patterns = conn.execute('''
            SELECT question_pattern, successful_response, feedback_score, usage_count
            FROM learning_data 
            WHERE feedback_score >= 0.7
            ORDER BY feedback_score DESC, usage_count DESC
            LIMIT 20
        ''').fetchall()
        conn.close()
        
        if learned_patterns:
            pattern_list = [{'question': p['question_pattern'], 'response': p['successful_response']} 
                          for p in learned_patterns]
            similar_patterns = semantic_similarity_search(message, pattern_list, threshold=0.3)
            
            if similar_patterns:
                # Enhance response with learned insights
                enhancement = f"\n\n💡 **Enhanced Insight** (Based on similar successful interactions):\n"
                best_pattern = similar_patterns[0]
                enhancement += f"{best_pattern['response'][:200]}..."
                
                if len(similar_patterns) > 1:
                    enhancement += f"\n\n*Found {len(similar_patterns)} similar successful interactions*"
                
                return base_response + enhancement
        
        # Add sentiment-aware enhancement
        if sentiment_data['sentiment'] == 'negative' and sentiment_data['confidence'] > 0.3:
            empathy_note = "\n\n😊 **Note:** I understand this might be challenging. I'm here to help make it easier!"
            return base_response + empathy_note
        elif sentiment_data['sentiment'] == 'positive' and sentiment_data['confidence'] > 0.3:
            encouragement = "\n\n🌟 **Great!** I'm excited to help you with this!"
            return base_response + encouragement
        
        return base_response
        
    except Exception as e:
        logger.warning(f"Error enhancing response: {e}")
        return base_response

@app.route('/')
def index():
    """Serve the main chat interface"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    """Serve static files (CSS, JS, etc.)"""
    return send_from_directory('.', filename)

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get all conversations for the user"""
    try:
        conn = get_db_connection()
        
        # Get conversations ordered by updated_at
        conversations = conn.execute('''
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            GROUP BY c.id, c.title, c.created_at, c.updated_at
            ORDER BY c.updated_at DESC
        ''').fetchall()
        
        conn.close()
        
        # Group conversations by time period
        now = datetime.now()
        today = now.date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        result = {
            'today': [],
            'yesterday': [],
            'last_week': [],
            'older': []
        }
        
        for conv in conversations:
            updated_at = datetime.fromisoformat(conv['updated_at'].replace('Z', '+00:00'))
            conv_date = updated_at.date()
            
            conversation_data = {
                'id': conv['id'],
                'title': conv['title'],
                'created_at': conv['created_at'],
                'updated_at': conv['updated_at'],
                'message_count': conv['message_count']
            }
            
            if conv_date == today:
                result['today'].append(conversation_data)
            elif conv_date == yesterday:
                result['yesterday'].append(conversation_data)
            elif conv_date > week_ago:
                result['last_week'].append(conversation_data)
            else:
                result['older'].append(conversation_data)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({'error': 'Failed to get conversations'}), 500

@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    """Create a new conversation"""
    try:
        data = request.get_json()
        
        conversation_id = str(uuid.uuid4())
        title = data.get('title', 'New Conversation')
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO conversations (id, title)
            VALUES (?, ?)
        ''', (conversation_id, title))
        conn.commit()
        conn.close()
        
        return jsonify({
            'id': conversation_id,
            'title': title,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        return jsonify({'error': 'Failed to create conversation'}), 500

@app.route('/api/conversations/<conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    """Get all messages for a conversation"""
    try:
        conn = get_db_connection()
        
        messages = conn.execute('''
            SELECT id, role, content, timestamp
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        ''', (conversation_id,)).fetchall()
        
        conn.close()
        
        return jsonify([{
            'id': msg['id'],
            'role': msg['role'],
            'content': msg['content'],
            'timestamp': msg['timestamp']
        } for msg in messages])
    
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return jsonify({'error': 'Failed to get messages'}), 500

@app.route('/api/conversations/<conversation_id>/messages', methods=['POST'])
def send_message(conversation_id):
    try:
        # Get JSON data with better error handling
        data = request.get_json()
        if not isinstance(data, dict):
            logger.warning(f"Invalid request data type: {type(data)}")
            data = {}
        
        message = data.get('message', '').strip()
        active_tools = data.get('tools', [])  # Expecting a list of tool names
        
        # Debug logging
        logger.info(f"📨 Received message from conversation {conversation_id}: {message[:50]}...")
        logger.info(f"🔧 Active tools: {active_tools}")
        logger.info(f"🌐 Request origin: {request.headers.get('Origin', 'Unknown')}")
        
        if not message:
            logger.warning("Empty message received")
            return jsonify({'error': 'Message cannot be empty'}), 400
    
    except Exception as e:
        logger.error(f"❌ Error parsing request: {e}")
        return jsonify({'error': 'Invalid request format'}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        # Check if conversation exists
        conv = conn.execute('''
            SELECT id, title FROM conversations WHERE id = ?
        ''', (conversation_id,)).fetchone()
        if not conv:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Get recent chat history for context
        history_messages = conn.execute('''
            SELECT role, content FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        ''', (conversation_id,)).fetchall()
        chat_history = [{"role": msg["role"], "content": msg["content"]} for msg in history_messages]
        
        # Add user message
        user_msg_id = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO messages (id, conversation_id, role, content)
            VALUES (?, ?, ?, ?)
        ''', (user_msg_id, conversation_id, 'user', message))
        conn.commit()
        
        # Generate AI response with chat history context and tool toggles
        ai_response_data = generate_ai_response(message, conversation_id, chat_history, active_tools)
        
        # Handle both string and dict responses
        if isinstance(ai_response_data, dict):
            ai_response = ai_response_data.get('content', '')
            thinking_data = ai_response_data.get('thinking', None)
        else:
            ai_response = ai_response_data
            thinking_data = None
        
        ai_msg_id = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO messages (id, conversation_id, role, content)
            VALUES (?, ?, ?, ?)
        ''', (ai_msg_id, conversation_id, 'assistant', ai_response))
        
        # Store Q&A for adaptive learning
        with open('learning_data.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'question': message,
                'answer': ai_response,
                'timestamp': datetime.now().isoformat(),
                'tools': active_tools
            }) + '\n')
        
        # Update conversation title if it's the first message
        message_count = conn.execute('''
            SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?
        ''', (conversation_id,)).fetchone()['count']
        if message_count <= 2:  # First exchange
            new_title = generate_chat_title(message)
            conn.execute('''
                UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_title, conversation_id))
        else:
            # Just update the timestamp
            conn.execute('''
                UPDATE conversations SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (conversation_id,))
        
        conn.commit()
        
        response_data = {
            'user_message': {
                'id': user_msg_id,
                'role': 'user',
                'content': message,
                'timestamp': datetime.now().isoformat()
            },
            'assistant_message': {
                'id': ai_msg_id,
                'role': 'assistant',
                'content': ai_response,
                'thinking': thinking_data,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        logger.info(f"✅ Successfully processed message, response length: {len(ai_response)} chars")
        return jsonify(response_data), 200
    
    except Exception as e:
        logger.error(f"❌ Error in send_message: {e}", exc_info=True)
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({'error': f'Failed to process message: {str(e)}'}), 500
    
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass
@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Delete a conversation and all its messages"""
    try:
        conn = get_db_connection()
        
        # Delete messages first
        conn.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
        
        # Delete conversation
        conn.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        return jsonify({'error': 'Failed to delete conversation'}), 500

@app.route('/api/conversations/<conversation_id>/clear', methods=['POST'])
def clear_conversation(conversation_id):
    """Clear all messages from a conversation"""
    try:
        conn = get_db_connection()
        
        # Delete all messages
        conn.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
        
        # Update conversation timestamp
        conn.execute('''
            UPDATE conversations SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (conversation_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        return jsonify({'error': 'Failed to clear conversation'}), 500

@app.route('/api/conversations/<conversation_id>', methods=['PATCH'])
def update_conversation(conversation_id):
    """Update a conversation (e.g., rename)"""
    try:
        data = request.get_json()
        title = data.get('title')
        
        if not title or not title.strip():
            return jsonify({'error': 'Title cannot be empty'}), 400
        
        conn = get_db_connection()
        
        # Check if conversation exists
        conv = conn.execute('''
            SELECT id FROM conversations WHERE id = ?
        ''', (conversation_id,)).fetchone()
        
        if not conv:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Update the title
        conn.execute('''
            UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (title.strip(), conversation_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'title': title.strip()})
    
    except Exception as e:
        logger.error(f"Error updating conversation: {e}")
        return jsonify({'error': 'Failed to update conversation'}), 500

@app.route('/api/models', methods=['GET'])
def get_models():
    """Get available models (branded as Companion AI capabilities)"""
    try:
        return jsonify({
            'status': 'success',
            'data': {
                'primary_model': 'Companion AI',
                'description': 'Advanced Multi-Engine AI Assistant',
                'capabilities': [
                    'General Conversation & Knowledge',
                    'Step-by-Step Reasoning (Think Mode)',
                    'Web Search & Research (Deep Search)',
                    'Code Generation & Analysis',
                    'File Upload & GitHub Integration'
                ],
                'search_engines': [
                    'DuckDuckGo', 'SearX', 'Startpage', 'Bing'
                ],
                'features': [
                    'Multi-engine web search',
                    'Intelligent model routing',
                    'Automatic fallback systems',
                    'Performance optimization',
                    'Response caching'
                ]
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get API status and performance metrics"""
    try:
        status = api_wrapper.get_api_status()
        return jsonify({
            'status': 'success',
            'data': status
        }), 200
    except Exception as e:
        logger.error(f"Error getting API status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/cache/stats', methods=['GET'])
def cache_stats():
    """Get response cache statistics"""
    try:
        stats = response_cache.get_stats()
        return jsonify({
            'status': 'success',
            'cache': stats
        }), 200
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Clear the response cache"""
    try:
        response_cache.clear()
        logger.info("🧹 Cache cleared via API")
        return jsonify({
            'status': 'success',
            'message': 'Cache cleared successfully'
        }), 200
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/feedback', methods=['POST'])
def feedback():
    data = request.get_json()  # Ensure data is a dict
    conversation_id = data.get('conversation_id')
    message_id = data.get('message_id')
    feedback_type = data.get('feedback_type')  # 'like' or 'dislike'
    message_content = data.get('message_content', '')
    comment = data.get('comment', '')
    
    # Convert feedback_type to rating for database compatibility
    rating = 5 if feedback_type == 'like' else 1 if feedback_type == 'dislike' else 3
    
    try:
        # Save feedback to database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO feedback 
            (conversation_id, message_id, feedback_type, rating, comment, timestamp)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (conversation_id, message_id, feedback_type, rating, comment))
        
        # If positive feedback, consider this for adaptive learning
        if feedback_type == 'like' and message_content:
            try:
                # Extract key patterns from the user's question for learning
                # This is a simplified approach - you could use more sophisticated NLP
                patterns = extract_learning_patterns(message_content)
                
                # Save successful response for future learning
                cursor.execute("""
                    INSERT OR REPLACE INTO learning_data 
                    (pattern, response, confidence, usage_count, last_used)
                    VALUES (?, ?, 1.0, 1, datetime('now'))
                """, (patterns[0] if patterns else message_content[:100], message_content))
                
                logger.info(f"Added successful response to learning database: {message_content[:50]}...")
                
            except Exception as learning_error:
                logger.warning(f"Failed to save to learning database: {learning_error}")
        
        conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Thank you for your feedback!'
        })
    
    except Exception as e:
        logger.error(f"Error adding feedback: {e}")
        return jsonify({'error': 'Failed to add feedback'}), 500

@app.route('/api/conversations/<conversation_id>/regenerate', methods=['POST'])
def regenerate_response(conversation_id):
    """Regenerate the last AI response for a given message"""
    try:
        data = request.json
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get conversation history for context
        cursor.execute("""
            SELECT role, content FROM messages 
            WHERE conversation_id = ? 
            ORDER BY timestamp ASC
        """, (conversation_id,))
        
        chat_history = []
        for role, content in cursor.fetchall():
            chat_history.append({"role": role, "content": content})
        
        # Check for learned response first
        learned_response = find_learned_response(message)
        is_learned = bool(learned_response)
        
        if learned_response:
            ai_response = learned_response
            logger.info(f"Using learned response for: {message[:50]}...")
        else:
            # Generate new AI response
            ai_response = generate_ai_response(message, conversation_id, chat_history)
        
        # Generate unique message ID
        message_id = f"msg_{int(time.time() * 1000)}_{conversation_id}"
        
        # Save the regenerated response (remove old assistant message and add new one)
        cursor.execute("""
            DELETE FROM messages 
            WHERE conversation_id = ? AND role = 'assistant'
            AND id = (
                SELECT id FROM messages 
                WHERE conversation_id = ? AND role = 'assistant'
                ORDER BY timestamp DESC LIMIT 1
            )
        """, (conversation_id, conversation_id))
        
        cursor.execute("""
            INSERT INTO messages (id, conversation_id, role, content, timestamp) 
            VALUES (?, ?, 'assistant', ?, datetime('now'))
        """, (message_id, conversation_id, ai_response))
        
        # Update conversation timestamp
        cursor.execute("""
            UPDATE conversations 
            SET updated_at = datetime('now') 
            WHERE id = ?
        """, (conversation_id,))
        
        conn.commit()
        
        return jsonify({
            'message_id': message_id,
            'assistant_message': {
                'content': ai_response,
                'role': 'assistant'
            },
            'is_learned': is_learned,
            'conversation_id': conversation_id
        })
        
    except Exception as e:
        logger.error(f"Error regenerating response: {e}")
        return jsonify({'error': 'Failed to regenerate response'}), 500

@app.route('/api/analytics/feedback', methods=['GET'])
def get_feedback_analytics():
    """Get feedback analytics"""
    try:
        conn = get_db_connection()
        
        # Get overall feedback stats
        stats = conn.execute('''
            SELECT 
                COUNT(*) as total_feedback,
                AVG(rating) as average_rating,
                COUNT(CASE WHEN rating >= 4 THEN 1 END) as positive_feedback,
                COUNT(CASE WHEN rating <= 2 THEN 1 END) as negative_feedback
            FROM feedback
        ''').fetchone()
        
        # Get recent feedback
        recent_feedback = conn.execute('''
            SELECT f.rating, f.comment, f.timestamp, m.content as message_content
            FROM feedback f
            JOIN messages m ON f.message_id = m.id
            ORDER BY f.timestamp DESC
            LIMIT 10
        ''').fetchall()
        
        # Get learning data stats
        learning_stats = conn.execute('''
            SELECT 
                COUNT(*) as total_patterns,
                SUM(usage_count) as total_usage,
                AVG(feedback_score) as avg_learning_score
            FROM learning_data
        ''').fetchone()
        
        conn.close()
        
        return jsonify({
            'feedback_stats': {
                'total_feedback': stats['total_feedback'],
                'average_rating': round(stats['average_rating'] or 0, 2),
                'positive_feedback': stats['positive_feedback'],
                'negative_feedback': stats['negative_feedback']
            },
            'recent_feedback': [{
                'rating': fb['rating'],
                'comment': fb['comment'],
                'timestamp': fb['timestamp'],
                'message_preview': fb['message_content'][:100] + '...' if len(fb['message_content']) > 100 else fb['message_content']
            } for fb in recent_feedback],
            'learning_stats': {
                'total_patterns': learning_stats['total_patterns'],
                'total_usage': learning_stats['total_usage'],
                'avg_learning_score': round(learning_stats['avg_learning_score'] or 0, 2)
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting feedback analytics: {e}")
        return jsonify({'error': 'Failed to get analytics'}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'companion-chat-backend'})

@app.route('/api/docs', methods=['GET'])
def api_documentation():
    """API Documentation endpoint"""
    api_docs = {
        "name": "Companion AI Chat API",
        "version": "3.0",
        "description": "Advanced AI chat interface with NLP, machine learning, and web search capabilities",
        "base_url": request.host_url.rstrip('/'),
        "endpoints": {
            "conversations": {
                "GET /api/conversations": {
                    "description": "Get all conversations for the user",
                    "response": "Array of conversation objects with id, title, created_at, updated_at, message_count"
                },
                "POST /api/conversations": {
                    "description": "Create a new conversation",
                    "response": "New conversation object with generated ID"
                },
                "DELETE /api/conversations/{id}": {
                    "description": "Delete a conversation and all its messages",
                    "response": "Success confirmation"
                },
                "PATCH /api/conversations/{id}": {
                    "description": "Update conversation (rename)",
                    "body": {"title": "New conversation title"},
                    "response": "Updated conversation object"
                }
            },
            "messages": {
                "GET /api/conversations/{id}/messages": {
                    "description": "Get all messages in a conversation",
                    "response": "Array of message objects with id, role, content, timestamp"
                },
                "POST /api/conversations/{id}/messages": {
                    "description": "Send a new message and get AI response",
                    "body": {
                        "message": "User message text",
                        "active_tools": ["Optional array of tools: web, think, deepsearch, code"]
                    },
                    "response": "AI response with enhanced capabilities"
                }
            },
            "features": {
                "POST /api/feedback": {
                    "description": "Submit feedback for a message",
                    "body": {
                        "message_id": "Message ID",
                        "conversation_id": "Conversation ID", 
                        "rating": "1-5 rating",
                        "comment": "Optional feedback comment"
                    },
                    "response": "Feedback confirmation"
                }
            }
        },
        "features": {
            "ai_models": [
                "OpenAI GPT-5",
                "Anthropic Claude 3.5 Haiku",
                "DeepSeek R1 (Reasoning)",
                "Perplexity Sonar (Research)",
                "Qwen3 Coder (Programming)"
            ],
            "capabilities": [
                "Natural Language Processing (NLP) with sentiment analysis",
                "Reinforcement Learning from user feedback",
                "Semantic similarity search for improved responses", 
                "Real-time web search and content scraping",
                "Adaptive learning and response enhancement",
                "Multiple AI model fallback system",
                "Thinking process visualization (DeepSeek R1)",
                "Advanced conversation management"
            ],
            "tools": {
                "web": "Real-time web search with DuckDuckGo API and content scraping",
                "think": "Step-by-step reasoning with DeepSeek R1 models",
                "deepsearch": "Comprehensive research mode with multiple sources",
                "code": "Specialized programming assistance with code-focused models"
            }
        },
        "authentication": "None required for web interface",
        "rate_limits": "Built-in intelligent rate limiting per model",
        "response_format": "JSON with content, optional thinking data, and metadata"
    }
    
    return jsonify(api_docs)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "nlp_available": NLP_AVAILABLE,
            "models_configured": len(OPENROUTER_CONFIG.get('models', {})),
            "knowledge_cache_size": len(KNOWLEDGE_CACHE),
            "trending_topics": len(TRENDING_TOPICS),
            "last_cache_update": LAST_UPDATE.isoformat() if LAST_UPDATE else None
        },
        "version": "3.0"
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        conn = get_db_connection()
        
        # Get conversation stats
        total_conversations = conn.execute('SELECT COUNT(*) as count FROM conversations').fetchone()['count']
        total_messages = conn.execute('SELECT COUNT(*) as count FROM messages').fetchone()['count']
        
        # Get learning stats
        learning_patterns = conn.execute('SELECT COUNT(*) as count FROM learning_data').fetchone()['count']
        high_scoring_patterns = conn.execute('SELECT COUNT(*) as count FROM learning_data WHERE feedback_score >= 0.7').fetchone()['count']
        
        conn.close()
        
        return jsonify({
            "conversations": {
                "total": total_conversations,
                "total_messages": total_messages,
                "avg_messages_per_conversation": round(total_messages / max(total_conversations, 1), 2)
            },
            "learning": {
                "total_patterns": learning_patterns,
                "high_quality_patterns": high_scoring_patterns,
                "learning_success_rate": round((high_scoring_patterns / max(learning_patterns, 1)) * 100, 2)
            },
            "knowledge_cache": {
                "cached_topics": len(KNOWLEDGE_CACHE),
                "trending_items": len(TRENDING_TOPICS),
                "nlp_enabled": NLP_AVAILABLE
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": "Unable to get statistics"}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file uploads (images, documents, etc.)"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file type and size
        allowed_extensions = {'txt', 'pdf', 'docx', 'md', 'py', 'js', 'html', 'css', 'json', 'xml', 'csv', 'jpg', 'jpeg', 'png', 'gif', 'svg'}
        max_size = 10 * 1024 * 1024  # 10MB
        
        filename = file.filename.lower()
        if not any(filename.endswith('.' + ext) for ext in allowed_extensions):
            return jsonify({'error': 'File type not supported'}), 400
        
        # Read file content
        file_content = file.read()
        if len(file_content) > max_size:
            return jsonify({'error': 'File too large (max 10MB)'}), 400
        
        # Process based on file type
        processed_content = ""
        file_type = filename.split('.')[-1]
        
        if file_type in ['txt', 'md', 'py', 'js', 'html', 'css', 'json', 'xml', 'csv']:
            # Text files - read content directly
            processed_content = file_content.decode('utf-8', errors='ignore')
        elif file_type == 'pdf':
            # PDF processing would require PyPDF2 or similar
            processed_content = "PDF file uploaded. Content extraction requires additional libraries."
        elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'svg']:
            # Image files - for now just note the upload
            processed_content = f"Image file uploaded: {file.filename} ({len(file_content)} bytes)"
        
        # Store file info temporarily (in a real app, you'd use proper file storage)
        file_id = str(uuid.uuid4())
        
        return jsonify({
            'success': True,
            'file_id': file_id,
            'filename': file.filename,
            'type': file_type,
            'size': len(file_content),
            'preview': processed_content[:500] + '...' if len(processed_content) > 500 else processed_content
        })
    
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'error': 'Failed to upload file'}), 500

@app.route('/api/github/connect', methods=['POST'])
def connect_github():
    """Connect to GitHub repository"""
    try:
        data = request.get_json()
        repo_url = data.get('repo_url', '').strip()
        
        if not repo_url:
            return jsonify({'error': 'Repository URL required'}), 400
        
        # Extract owner and repo from URL
        repo_url = repo_url.replace('https://github.com/', '').replace('github.com/', '')
        
        if '/' not in repo_url:
            return jsonify({'error': 'Invalid repository format. Use: owner/repo'}), 400
        
        owner, repo = repo_url.split('/', 1)
        
        # Fetch repository information using GitHub API
        github_api_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {'Accept': 'application/vnd.github.v3+json'}
        
        response = pyrequests.get(github_api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            repo_data = response.json()
            
            return jsonify({
                'success': True,
                'repository': {
                    'name': repo_data['name'],
                    'full_name': repo_data['full_name'],
                    'description': repo_data.get('description', ''),
                    'language': repo_data.get('language', ''),
                    'stars': repo_data['stargazers_count'],
                    'forks': repo_data['forks_count'],
                    'url': repo_data['html_url']
                }
            })
        
        elif response.status_code == 404:
            return jsonify({'error': 'Repository not found or private'}), 404
        else:
            return jsonify({'error': f'GitHub API error: {response.status_code}'}), 500
    
    except Exception as e:
        logger.error(f"Error connecting to GitHub: {e}")
        return jsonify({'error': 'Failed to connect to GitHub repository'}), 500

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Start response cache cleanup thread
    logger.info("📦 Starting response cache system...")
    start_cache_cleanup_thread()
    logger.info(f"✅ Response cache initialized: {response_cache.get_info()}")
    
    # Initialize Neural Layer Pipeline
    if NEURAL_LAYER_AVAILABLE:
        try:
            logger.info("🧠 Initializing Neural Layer Pipeline...")
            neural_pipeline = LaptopNeuralPipeline(api_wrapper, search_wrapper)
            logger.info("✅ Neural layer initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize neural layer: {e}")
            neural_pipeline = None
    
    # Start background data gathering for enhanced responses
    logger.info("🚀 Initializing AI companion with enhanced learning capabilities...")
    startup_thread = threading.Thread(target=startup_data_gathering, daemon=True)
    startup_thread.start()
    
    # Schedule periodic knowledge updates (every 6 hours)
    schedule.every(6).hours.do(update_knowledge_cache)
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Start the server
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Companion Chat Backend on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
