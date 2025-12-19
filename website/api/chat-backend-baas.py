# --- LOGOUT ENDPOINTS ---
# (Moved below app and dependencies)
#!/usr/bin/env python3
"""
Companion Chat Backend with BaaS Integration
=============================================

Clean, modern backend powered by Companion BaaS (Brain as a Service)

Changes from original:
- ✅ Integrated Companion BaaS for all AI logic
- ✅ Removed 2000+ lines of AI complexity
- ✅ Kept all essential features (auth, DB, conversations)
- ✅ Cleaner, more maintainable code
- ✅ Same API endpoints (backward compatible)
"""

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import json
import os
import sys
import uuid
from datetime import datetime, timedelta
import sqlite3
import logging
from queue import Queue
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
import asyncio
import threading
import time
import concurrent.futures
import re
import traceback
from urllib.parse import urlparse

# Add paths for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

# ============================================================================
# COMPANION BAAS INTEGRATION - Now with AGI! 🧠🎊
# ============================================================================
from companion_baas.sdk import BrainClient

# Initialize the AI Brain for chatbot with AGI features
companion_brain = BrainClient(
    app_type="chatbot",
    enable_caching=True,
    enable_search=True,
    enable_learning=True,
    enable_agi=True,         # Enable AGI features
    enable_autonomy=False     # 🔒 Safe mode: Autonomy disabled by default
)
logger = logging.getLogger(__name__)
logger.info("🧠 Companion Brain initialized with AGI features!")
logger.info(f"🎭 AGI Status: {companion_brain.get_agi_status()['agi_enabled']}")
if companion_brain.get_personality():
    logger.info(f"🎨 Personality: {companion_brain.get_personality()['personality_id']}")

# ============================================================================
# KEEP: Authentication System
# ============================================================================
from auth_backend import auth_manager
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)

def get_token_from_request():
    """Extract token from Authorization header"""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None

def require_auth(f):
    """Decorator to require authentication for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        
        user = auth_manager.get_user_by_token(token)
        if not user:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Store user in request context
        request.current_user = user
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__, template_folder='.')

# Configure CORS
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

# Configure Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Thread pool for concurrent AI processing
ai_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="ai_worker")

# ============================================================================
# KEEP: Database Configuration
# ============================================================================
DATABASE = 'chat_history.db'

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT DEFAULT 'web_user'
        )
    ''')
    
    # Messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT DEFAULT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    ''')
    
    # Feedback table
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
    return_db_connection(conn)

# Database connection pool for better concurrency
class DatabaseConnectionPool:
    def __init__(self, database_path, max_connections=5):
        self.database_path = database_path
        self.max_connections = max_connections
        self.connections = Queue(maxsize=max_connections)
        self.lock = Lock()
        
        # Pre-populate the pool
        for _ in range(max_connections):
            conn = sqlite3.connect(database_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.connections.put(conn)
    
    def get_connection(self):
        """Get a connection from the pool"""
        return self.connections.get()
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        if conn:
            self.connections.put(conn)
    
    def close_all(self):
        """Close all connections in the pool"""
        while not self.connections.empty():
            try:
                conn = self.connections.get_nowait()
                return_db_connection(conn)
            except:
                pass

# Initialize database connection pool
db_pool = None

def init_db_pool(database_path):
    """Initialize the database connection pool"""
    global db_pool
    db_pool = DatabaseConnectionPool(database_path)
    return db_pool

def get_db_connection():
    """Get database connection from pool"""
    if db_pool is None:
        # Fallback to direct connection if pool not initialized
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn
    return db_pool.get_connection()

def return_db_connection(conn):
    """Return connection to pool"""
    if db_pool and conn:
        db_pool.return_connection(conn)
    elif conn:
        # If no pool, just close the connection
        conn.close()

def generate_chat_title(message):
    """Generate a title for the chat based on the first message"""
    # Simple title generation - take first few words
    words = message.strip().split()[:6]  # Max 6 words
    title = ' '.join(words)
    if len(message) > len(title):
        title += "..."
    return title[:50]  # Max 50 chars

def process_ai_request(message, conversation_id, mapped_tools, active_tools):
    """Process AI request in a separate thread for concurrency"""
    brain_response = companion_brain.chat(
        message=message,
        conversation_id=conversation_id,
        tools=mapped_tools
    )
    
    # Handle brain response with fallbacks
    if not brain_response or not brain_response.get('success'):
        error_msg = brain_response.get('error', 'Unknown brain error') if brain_response else 'No response from brain'
        logger.error(f"❌ Brain failed: {error_msg}")
        
        # Try fallback with basic tools if agent/deepsearch failed
        if any(tool in ['agent', 'deepsearch'] for tool in active_tools):
            logger.info("🔄 Trying fallback with basic search...")
            fallback_response = companion_brain.chat(
                message=message,
                conversation_id=conversation_id,
                tools=["web"]  # Fallback to basic web search
            )
            if fallback_response and fallback_response.get('success'):
                brain_response = fallback_response
                logger.info("✅ Fallback successful")
            else:
                logger.error("❌ Fallback also failed")
    
    return brain_response
    """Generate a title for the chat based on the first message"""
    title = message.strip()[:50]
    if len(message) > 50:
        title += "..."
    return title

# ============================================================================
# KEEP: Authentication Middleware
# ============================================================================
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
        
        request.current_user = user
        return f(*args, **kwargs)
    
    return decorated_function

# ============================================================================
# KEEP: Authentication Routes
# ============================================================================
@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()
        
        # Input validation
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        email = data.get('email', '').strip().lower()
        name = data.get('name', '').strip()
        password = data.get('password', '')
        newsletter = data.get('newsletter', False)
        
        # Validate email
        if not email:
            return jsonify({'success': False, 'message': 'Email is required'}), 400
        if len(email) > 254:  # RFC 5321 limit
            return jsonify({'success': False, 'message': 'Email too long'}), 400
        if '@' not in email or '.' not in email:
            return jsonify({'success': False, 'message': 'Invalid email format'}), 400
        
        # Validate name
        if not name:
            return jsonify({'success': False, 'message': 'Name is required'}), 400
        if len(name) > 100:
            return jsonify({'success': False, 'message': 'Name too long'}), 400
        if not all(c.isalnum() or c in ' -_.' for c in name):
            return jsonify({'success': False, 'message': 'Name contains invalid characters'}), 400
        
        # Validate password
        if not password or len(password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters'}), 400
        if len(password) > 128:
            return jsonify({'success': False, 'message': 'Password too long'}), 400
        
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        success, message, user_data = auth_manager.register_user(
            email, name, password, newsletter
        )
        
        if success:
            logger.info(f"✅ New user registered: {email}")
            return jsonify({
                'success': True,
                'message': message,
                'data': {
                    'user': {
                        'id': user_data['user_id'],
                        'email': email,
                        'name': name
                    }
                }
            }), 201
        else:
            return jsonify({'success': False, 'message': message}), 400
            
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
        
        # Input validation
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        remember = data.get('remember', False)
        
        # Validate email
        if not email:
            return jsonify({'success': False, 'message': 'Email is required'}), 400
        if len(email) > 254:
            return jsonify({'success': False, 'message': 'Email too long'}), 400
        
        # Validate password
        if not password:
            return jsonify({'success': False, 'message': 'Password is required'}), 400
        if len(password) > 128:
            return jsonify({'success': False, 'message': 'Password too long'}), 400
        
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        success, message, auth_data = auth_manager.login_user(
            email, password, ip_address, user_agent, remember
        )
        
        if success:
            logger.info(f"✅ User logged in: {email}")
            return jsonify({
                'success': True,
                'message': message,
                'data': {
                    'token': auth_data['token'],
                    'user': auth_data['user']
                }
            }), 200
        else:
            return jsonify({'success': False, 'message': message}), 401
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            'success': False,
            'message': 'Login failed due to server error'
        }), 500

@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    """Check authentication status"""
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        
        # Extract token from "Bearer <token>"
        if token.startswith('Bearer '):
            token = token[7:]
        
        user_data = auth_manager.get_user_by_token(token)
        if not user_data:
            return jsonify({'error': 'Invalid token'}), 401
        
        return jsonify({'user': user_data}), 200
        
    except Exception as e:
        logger.error(f"Auth check error: {e}")
        return jsonify({'error': 'Authentication check failed'}), 401

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
            return jsonify({'success': True, 'message': message}), 200
        else:
            return jsonify({'success': False, 'message': message}), 400
            
    except Exception as e:
        logger.error(f"Change password error: {e}")
        return jsonify({
            'success': False,
            'message': 'Password change failed due to server error'
        }), 500

# ============================================================================
# NEW: Chat Endpoints Using Companion BaaS 🧠
# ============================================================================

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get all conversations grouped by time"""
    try:
        conn = get_db_connection()
        
        # Get all conversations ordered by most recent
        conversations = conn.execute('''
            SELECT id, title, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC
        ''').fetchall()
        
        return_db_connection(conn)
        
        # Group by time periods
        now = datetime.now()
        today = []
        yesterday = []
        last_week = []
        older = []
        
        for conv in conversations:
            updated = datetime.fromisoformat(conv['updated_at'])
            conv_dict = {
                'id': conv['id'],
                'title': conv['title'],
                'created_at': conv['created_at'],
                'updated_at': conv['updated_at']
            }
            
            if updated.date() == now.date():
                today.append(conv_dict)
            elif updated.date() == (now - timedelta(days=1)).date():
                yesterday.append(conv_dict)
            elif updated.date() >= (now - timedelta(days=7)).date():
                last_week.append(conv_dict)
            else:
                older.append(conv_dict)
        
        return jsonify({
            'today': today,
            'yesterday': yesterday,
            'last_week': last_week,
            'older': older
        })
    
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({'error': 'Failed to get conversations'}), 500

@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    """Create a new conversation"""
    try:
        data = request.get_json() or {}
        title = data.get('title', 'New Chat')
        
        conn = get_db_connection()
        conversation_id = str(uuid.uuid4())
        
        conn.execute('''
            INSERT INTO conversations (id, title)
            VALUES (?, ?)
        ''', (conversation_id, title))
        
        conn.commit()
        return_db_connection(conn)
        
        utc_now = datetime.utcnow().isoformat() + 'Z'
        return jsonify({
            'id': conversation_id,
            'title': title,
            'created_at': utc_now,
            'updated_at': utc_now
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        return jsonify({'error': 'Failed to create conversation'}), 500

@app.route('/api/conversations/<conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    """Get all messages for a conversation"""
    try:
        conn = get_db_connection()
        
        # Check if conversation exists
        conv = conn.execute(
            'SELECT id FROM conversations WHERE id = ?',
            (conversation_id,)
        ).fetchone()
        
        if not conv:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Get messages
        messages = conn.execute('''
            SELECT id, role, content, timestamp, metadata
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        ''', (conversation_id,)).fetchall()
        
        return_db_connection(conn)
        
        return jsonify({
            'messages': [
                {
                    'id': msg['id'],
                    'role': msg['role'],
                    'content': msg['content'],
                    'timestamp': msg['timestamp'],
                    'metadata': json.loads(msg['metadata']) if msg['metadata'] else None
                }
                for msg in messages
            ]
        })
    
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return jsonify({'error': 'Failed to get messages'}), 500

@app.route('/api/conversations/<conversation_id>/messages', methods=['POST'])
@limiter.limit("10 per minute")
def send_message(conversation_id):
    """
    Send a message and get AI response using Companion BaaS 🧠
    
    This is the heart of the integration - OLD AI logic replaced with Brain!
    """
    try:
        # Parse request
        data = request.get_json()
        if not isinstance(data, dict):
            data = {}
        
        message = data.get('message', '').strip()
        active_tools = data.get('tools', [])
        
        # Input validation
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        if not isinstance(message, str):
            return jsonify({'error': 'Message must be a string'}), 400
        
        if len(message) > 10000:  # Reasonable limit
            return jsonify({'error': 'Message too long (max 10000 characters)'}), 400
        
        # Basic content validation - prevent obvious malicious content
        if any(char in message for char in ['<script', 'javascript:', 'onload=', 'onerror=']):
            return jsonify({'error': 'Invalid message content'}), 400
        
        if not isinstance(active_tools, list):
            return jsonify({'error': 'Tools must be a list'}), 400
        
        # Validate tool names
        valid_tools = ['search', 'deepsearch', 'agent', 'web', 'code', 'think', 'research']
        if any(tool not in valid_tools for tool in active_tools):
            return jsonify({'error': 'Invalid tool specified'}), 400
        
        logger.info(f"📨 Message to conversation {conversation_id}: {message[:50]}...")
        logger.info(f"🔧 Tools: {active_tools}")
        
        conn = get_db_connection()
        
        # Check if conversation exists
        conv = conn.execute(
            'SELECT id, title FROM conversations WHERE id = ?',
            (conversation_id,)
        ).fetchone()
        
        if not conv:
            return_db_connection(conn)
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Save user message
        user_msg_id = str(uuid.uuid4())
        utc_now = datetime.utcnow().isoformat() + 'Z'
        conn.execute('''
            INSERT INTO messages (id, conversation_id, role, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_msg_id, conversation_id, 'user', message, utc_now))
        conn.commit()
        
        # ====================================================================
        # 🧠 USE COMPANION BRAIN - This replaces 2000+ lines of AI logic!
        # ====================================================================
        
        # Special optimization for basic search tool
        if active_tools == ["search"]:
            logger.info("🔍 Using optimized search path for basic queries")
            # For basic search, use a faster model directly
            try:
                # Use the brain's direct Bytez method for faster response
                search_result = companion_brain.brain.use_bytez(message, task='search')
                if search_result['success']:
                    ai_response = search_result['response']
                    metadata = {
                        'session_id': companion_brain.brain.session_id,
                        'app_type': companion_brain.brain.app_type,
                        'response_time': search_result.get('response_time', 0),
                        'model': search_result.get('model', 'bytez-fast'),
                        'tool': 'search',
                        'optimized': True
                    }
                    
                    logger.info(f"✅ Optimized search response: {len(ai_response)} chars in {metadata['response_time']:.2f}s")
                    
                    # Save AI response
                    ai_msg_id = str(uuid.uuid4())
                    conn.execute('''
                        INSERT INTO messages (id, conversation_id, role, content, metadata)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (ai_msg_id, conversation_id, 'assistant', ai_response, json.dumps(metadata)))
                    
                    # Update conversation title if first message
                    message_count = conn.execute(
                        'SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?',
                        (conversation_id,)
                    ).fetchone()[0]
                    
                    if message_count == 1:  # Only the user message exists
                        # Generate title from first message
                        title_prompt = f"Generate a short, descriptive title (max 6 words) for this conversation starter: {message[:100]}..."
                        title_result = companion_brain.brain.use_bytez(title_prompt, task='title')
                        if title_result['success']:
                            new_title = title_result['response'].strip().strip('"').strip("'")[:50]
                            utc_now2 = datetime.utcnow().isoformat() + 'Z'
                            conn.execute(
                                'UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?',
                                (new_title, utc_now2, conversation_id)
                            )
                    
                    conn.commit()
                    return_db_connection(conn)
                    
                    utc_now3 = datetime.utcnow().isoformat() + 'Z'
                    return jsonify({
                        'assistant_message': {
                            'id': ai_msg_id,
                            'content': ai_response,
                            'role': 'assistant',
                            'timestamp': utc_now3,
                            'metadata': metadata,
                            'thinking': None
                        },
                        'user_message': {
                            'id': user_msg_id,
                            'content': message,
                            'role': 'user',
                            'timestamp': utc_now3
                        }
                    })
                else:
                    logger.warning("⚠️ Optimized search failed, falling back to full brain")
            except Exception as e:
                logger.warning(f"⚠️ Optimized search error: {e}, falling back to full brain")
        
        # Map new tool names to brain capabilities
        mapped_tools = []
        tool_mapping_log = []
        
        for tool in active_tools:
            if tool == "search":
                # Basic search: uses tiny LLM + web scraping + search engines
                mapped_tools.append("web")  # Map to basic web search
                tool_mapping_log.append(f"{tool}->web")
            elif tool == "deepsearch":
                # Deep search: uses chain of thoughts + breaks query into components using Groq + scraping + search engines
                mapped_tools.extend(["web", "think"])  # Map to web search + deep thinking
                tool_mapping_log.append(f"{tool}->web+think")
            elif tool == "agent":
                # Agent mode: combination of all capabilities in agentic way
                mapped_tools.extend(["web", "think", "code"])  # Map to full capabilities
                tool_mapping_log.append(f"{tool}->web+think+code")
            else:
                # Keep any unrecognized tools as-is for backward compatibility
                mapped_tools.append(tool)
                tool_mapping_log.append(f"{tool}->unchanged")
        
        logger.info(f"🔄 Tool mapping: {', '.join(tool_mapping_log)}")
        
        # Remove duplicates while preserving order
        seen = set()
        mapped_tools = [x for x in mapped_tools if not (x in seen or seen.add(x))]
        
        if not mapped_tools:
            logger.warning("⚠️ No valid tools mapped, using default web search")
            mapped_tools = ["web"]
        
        # For AGI processing, handle synchronously to avoid timeout issues
        # The thread pool is still used for non-AGI requests
        if any(tool in ['agent', 'deepsearch', 'agi'] for tool in active_tools) or companion_brain.brain.enable_agi:
            logger.info(f"🧠 AGI detected, processing synchronously: '{message[:50]}...'")
            try:
                brain_response = process_ai_request(
                    message=message,
                    conversation_id=conversation_id,
                    mapped_tools=mapped_tools,
                    active_tools=active_tools
                )
                logger.info(f"✅ AGI processing completed successfully")
            except Exception as e:
                logger.error(f"AGI processing error: {e}")
                brain_response = {
                    'success': False,
                    'error': 'AGI processing error',
                    'response': "I apologize, but I encountered an error processing your request. Please try again."
                }
        else:
            # Submit non-AGI processing to thread pool for concurrency
            future = ai_executor.submit(
                process_ai_request,
                message=message,
                conversation_id=conversation_id,
                mapped_tools=mapped_tools,
                active_tools=active_tools
            )

            try:
                logger.info(f"⏳ Starting AI processing for message: '{message[:50]}...'")
                brain_response = future.result(timeout=60)  # 1 minute for regular processing
                logger.info(f"✅ AI processing completed successfully")
            except concurrent.futures.TimeoutError:
                logger.warning("⚠️ AI processing timed out after 1 minute")
                brain_response = {
                    'success': False,
                    'error': 'AI processing timeout',
                    'response': "I apologize, but I encountered an error processing your request. Please try again."
                }
            except Exception as e:
                logger.error(f"AI processing error: {e}")
                brain_response = {
                    'success': False,
                    'error': 'AI processing timeout or error',
                    'response': "I apologize, but I encountered an error processing your request. Please try again."
                }
        
        if brain_response['success']:
            ai_response = brain_response['response']
            metadata = brain_response.get('metadata', {})
            
            logger.info(f"✅ Brain response: {len(ai_response)} chars")
            logger.info(f"📊 Model: {metadata.get('model', 'N/A')}, Time: {metadata.get('response_time', 0):.2f}s")
        else:
            # Fallback response
            ai_response = "I apologize, but I encountered an error processing your request. Please try again."
            metadata = {'error': brain_response.get('error', 'Unknown error')}
            logger.error(f"❌ Brain error: {metadata['error']}")
        
        # Save AI response
        ai_msg_id = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO messages (id, conversation_id, role, content, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', (ai_msg_id, conversation_id, 'assistant', ai_response, json.dumps(metadata)))
        
        # Update conversation title if first message
        message_count = conn.execute(
            'SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?',
            (conversation_id,)
        ).fetchone()['count']
        
        if message_count <= 2:  # First exchange
            new_title = generate_chat_title(message)
            conn.execute('''
                UPDATE conversations 
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_title, conversation_id))
        else:
            # Update timestamp
            conn.execute('''
                UPDATE conversations 
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (conversation_id,))
        
        conn.commit()
        return_db_connection(conn)
        
        # Return response
        return jsonify({
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
                'thinking': metadata.get('thinking_data'),
                'timestamp': datetime.now().isoformat(),
                'metadata': metadata
            }
        }), 200
    
    except ValueError as e:
        logger.warning(f"❌ Validation error in send_message: {e}")
        return jsonify({'error': f'Invalid input: {str(e)}'}), 400
    except TimeoutError as e:
        logger.error(f"❌ Timeout in send_message: {e}")
        return jsonify({'error': 'Request timed out. Please try again.'}), 504
    except Exception as e:
        logger.error(f"❌ Unexpected error in send_message: {e}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred. Please try again later.'}), 500

@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Delete a conversation and all its messages"""
    try:
        conn = get_db_connection()
        
        # Also clear brain history for this conversation
        companion_brain.clear_history(conversation_id=conversation_id)
        
        # Delete messages
        conn.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
        
        # Delete conversation
        conn.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
        
        conn.commit()
        return_db_connection(conn)
        
        logger.info(f"🗑️ Deleted conversation {conversation_id}")
        return jsonify({'success': True})
    
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        return jsonify({'error': 'Failed to delete conversation'}), 500

# ============================================================================
# NEW: Brain Statistics Endpoint
# ============================================================================

@app.route('/api/brain/stats', methods=['GET'])
def get_brain_stats():
    """Get Companion Brain statistics"""
    try:
        stats = companion_brain.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting brain stats: {e}")
        return jsonify({'error': 'Failed to get stats'}), 500

# ============================================================================
# AGI ENDPOINTS (Tier 4) - New Intelligence Features
# ============================================================================

@app.route('/api/agi/personality', methods=['GET'])
def get_agi_personality():
    """Get brain's current personality"""
    try:
        personality = companion_brain.get_personality()
        if personality:
            return jsonify({
                'success': True,
                'personality': personality
            })
        else:
            return jsonify({
                'success': False,
                'message': 'AGI features not enabled'
            }), 404
    except Exception as e:
        logger.error(f"Error getting personality: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agi/learning', methods=['GET'])
def get_agi_learning():
    """Get learning statistics"""
    try:
        stats = companion_brain.get_learning_stats()
        if stats:
            return jsonify({
                'success': True,
                'learning_stats': stats
            })
        else:
            return jsonify({
                'success': False,
                'message': 'AGI features not enabled'
            }), 404
    except Exception as e:
        logger.error(f"Error getting learning stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agi/status', methods=['GET'])
def get_agi_status():
    """Get comprehensive AGI system status"""
    try:
        status = companion_brain.get_agi_status()
        return jsonify({
            'success': True,
            'agi_status': status
        })
    except Exception as e:
        logger.error(f"Error getting AGI status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agi/teach', methods=['POST'])
def teach_concept():
    """Teach a new concept to the brain"""
    try:
        data = request.get_json()
        concept_name = data.get('concept')
        examples = data.get('examples', [])
        
        if not concept_name or not examples:
            return jsonify({'error': 'concept and examples required'}), 400
        
        success = companion_brain.teach_concept(concept_name, examples)
        
        return jsonify({
            'success': success,
            'message': f"Concept '{concept_name}' taught with {len(examples)} examples" if success else "Failed to teach concept"
        })
    except Exception as e:
        logger.error(f"Error teaching concept: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agi/think', methods=['POST'])
def agi_think():
    """Enhanced thinking with AGI features"""
    try:
        data = request.get_json()
        query = data.get('query')
        mode = data.get('mode', 'auto')
        
        if not query:
            return jsonify({'error': 'query required'}), 400
        
        result = companion_brain.think_with_agi(query, mode)
        
        return jsonify({
            'success': result.get('success', True),
            'response': result.get('response'),
            'agi_metadata': result.get('agi_metadata', {})
        })
    except Exception as e:
        logger.error(f"Error in AGI thinking: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agi/toggle', methods=['POST'])
def toggle_agi():
    """Enable or disable AGI features"""
    try:
        data = request.get_json()
        enable = data.get('enable', True)
        
        companion_brain.enable_agi(enable)
        
        return jsonify({
            'success': True,
            'message': f"AGI {'enabled' if enable else 'disabled'}",
            'agi_enabled': enable
        })
    except Exception as e:
        logger.error(f"Error toggling AGI: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# PERPLEXITY-STYLE SEARCH FEATURES
# ============================================================================

# Import web intelligence for Perplexity search
try:
    from companion_baas.web_intelligence import get_search_client
    SEARCH_AVAILABLE = True
    search_client = get_search_client()
    logger.info("✅ Web search client loaded for Perplexity features")
except Exception as e:
    SEARCH_AVAILABLE = False
    search_client = None
    logger.warning(f"⚠️ Web search not available: {e}")


def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return url


def extract_citations_from_sources(sources: list) -> list:
    """Extract citation-ready information from sources"""
    citations = []
    for idx, source in enumerate(sources, 1):
        citations.append({
            'id': idx,
            'title': source.get('title', 'Untitled'),
            'url': source.get('url', ''),
            'domain': extract_domain(source.get('url', '')),
            'snippet': source.get('snippet', source.get('abstract_text', ''))[:200]
        })
    return citations


def generate_cited_response(query: str, sources: list, pro_mode: bool = False) -> dict:
    """Generate AI response with citations using the Brain"""
    try:
        context_text = "\n\n".join([
            f"[{i + 1}] {source.get('title', 'Source')} ({source.get('url', '')})\n{source.get('snippet', source.get('abstract_text', ''))}"
            for i, source in enumerate(sources[:5])
        ])

        system_prompt = """You are a research assistant that provides comprehensive answers with citations.

IMPORTANT RULES:
1. Use inline citations [1], [2], etc. when referencing information from sources
2. Write in a clear, informative style
3. Synthesize information from multiple sources
4. Be objective and factual
5. If sources don't contain enough information, acknowledge it

Format your response with natural paragraphs and cite sources inline like this [1] or [2]."""

        user_prompt = f"""Query: {query}

Available Sources:
{context_text}

Provide a comprehensive answer to the query using the sources above. Include inline citations [1], [2], etc. when referencing specific information."""

        result = companion_brain.brain.think(
            message=user_prompt,
            context={'system_prompt': system_prompt},
            tools=['think'] if not pro_mode else ['think', 'web', 'research']
        )

        response_text = result.get('response', '')
        citations_used = list(set(re.findall(r'\[(\d+)\]', response_text)))
        citations_used = sorted([int(c) for c in citations_used if str(c).isdigit()])

        return {
            'success': True,
            'response': response_text,
            'citations_used': citations_used,
            'metadata': result.get('metadata', {})
        }
    except Exception as e:
        logger.error(f"Error generating cited response: {e}")
        return {
            'success': False,
            'error': str(e),
            'response': '',
            'citations_used': []
        }


def generate_follow_up_questions(query: str, response: str, sources: list) -> list:
    """Generate relevant follow-up questions"""
    try:
        prompt = f"""Based on this search query and response, generate 3-5 relevant follow-up questions that a user might want to explore next.

Original Query: {query}

Response Summary: {response[:300]}...

Generate 3-5 concise follow-up questions (one per line, no numbering):"""

        result = companion_brain.brain.think(
            message=prompt,
            context={'mode': 'follow_up_generation'},
            tools=['think']
        )

        questions_text = result.get('response', '')
        questions = [
            q.strip().strip('-•*').strip()
            for q in questions_text.split('\n')
            if q.strip() and len(q.strip()) > 10
        ]

        return questions[:5] if questions else [
            f"What are the implications of {query}?",
            f"How does {query} compare to alternatives?",
            f"What are the latest developments in {query}?"
        ]
    except Exception as e:
        logger.error(f"Error generating follow-up questions: {e}")
        return [
            f"Tell me more about {query}",
            f"What are the benefits of {query}?",
            f"How does {query} work?"
        ]


@app.route('/api/perplexity_search', methods=['POST'])
@limiter.limit("20 per minute")
def perplexity_search():
    """
    Perplexity-style search endpoint with cited sources

    Request: {"query": "search query", "pro_mode": false}
    Returns: {"success": true, "response": "...", "sources": [...], "citations": [...], "follow_up_questions": [...]}
    """
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        pro_mode = data.get('pro_mode', False)

        if not query:
            return jsonify({'success': False, 'error': 'Query is required'}), 400

        logger.info(f"🔍 Perplexity search: {query} (pro_mode={pro_mode})")

        if not SEARCH_AVAILABLE or not search_client:
            return jsonify({'success': False, 'error': 'Search service unavailable'}), 503

        # Step 1: Search the web
        search_results = search_client.search(query, limit=10)

        if not search_results.get('success'):
            return jsonify({'success': False, 'error': 'Search failed'}), 500

        # Extract sources
        sources = []

        instant_answer = search_results.get('instant_answer', {})
        if instant_answer.get('abstract_text'):
            sources.append({
                'title': instant_answer.get('heading') or 'Instant Answer',
                'url': instant_answer.get('abstract_url') or '',
                'snippet': instant_answer.get('abstract_text'),
                'abstract_text': instant_answer.get('abstract_text'),
                'source': instant_answer.get('abstract_source', 'DuckDuckGo')
            })

        related = search_results.get('related_topics', [])
        for topic in related[:9]:
            if topic.get('url'):
                sources.append({
                    'title': topic.get('title', 'Related Topic'),
                    'url': topic.get('url'),
                    'snippet': topic.get('title', ''),
                    'source': extract_domain(topic.get('url', ''))
                })

        if not sources:
            return jsonify({'success': False, 'error': 'No sources found'}), 404

        # Step 2: Generate citations
        citations = extract_citations_from_sources(sources)

        # Step 3: Generate AI response with citations
        ai_result = generate_cited_response(query, sources, pro_mode)

        if not ai_result.get('success'):
            return jsonify({'success': False, 'error': ai_result.get('error', 'Failed to generate response')}), 500

        response_text = ai_result.get('response', '')

        # Step 4: Generate follow-up questions
        follow_up_questions = generate_follow_up_questions(query, response_text, sources)

        return jsonify({
            'success': True,
            'query': query,
            'response': response_text,
            'sources': sources[:10],
            'citations': citations,
            'citations_used': ai_result.get('citations_used', []),
            'follow_up_questions': follow_up_questions,
            'metadata': {
                'pro_mode': pro_mode,
                'num_sources': len(sources),
                'timestamp': datetime.now().isoformat(),
                **ai_result.get('metadata', {})
            }
        })

    except Exception as e:
        logger.error(f"Perplexity search failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# KEEP: Static file serving
# ============================================================================

@app.route('/')
def serve_index():
    """Serve login page as entry point"""
    response = send_from_directory('.', 'login.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/home')
def serve_home():
    """Serve index.html landing page (requires auth)"""
    response = send_from_directory('.', 'index.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/chat')
def serve_chat():
    """Serve the chat interface (requires auth)"""
    response = send_from_directory('.', 'modern-demo.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response





@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('.', path)

@app.route('/api/admin/db-stats', methods=['GET'])
def get_database_stats():
    """Get database size and growth statistics"""
    conn = None
    try:
        conn = get_db_connection()
        
        # Get database file size
        db_path = os.path.join(os.path.dirname(__file__), 'chat.db')
        db_size_mb = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0
        
        # Get table statistics
        stats = {}
        tables = ['conversations', 'messages', 'feedback', 'users']
        
        for table in tables:
            count = conn.execute(f'SELECT COUNT(*) as count FROM {table}').fetchone()['count']
            stats[table] = count
            
        # Get oldest conversation
        oldest = conn.execute('''
            SELECT MIN(created_at) as oldest FROM conversations
        ''').fetchone()['oldest']
        
        return jsonify({
            'database_size_mb': round(db_size_mb, 2),
            'table_counts': stats,
            'oldest_conversation': oldest,
            'total_messages': stats.get('messages', 0),
            'total_conversations': stats.get('conversations', 0)
        }), 200
        
    except Exception as e:
        logger.error(f"Database stats error: {e}")
        return jsonify({'error': 'Failed to get database stats'}), 500
    finally:
        if conn is not None:
            return_db_connection(conn)
def cleanup_old_data():
    """Clean up old conversations and messages to prevent database bloat"""
    conn = None
    try:
        # Only allow cleanup of conversations older than 90 days
        cutoff_date = (datetime.now() - timedelta(days=90)).isoformat()
        
        conn = get_db_connection()
        
        # Get count of conversations to be deleted
        old_conversations = conn.execute('''
            SELECT COUNT(*) as count FROM conversations 
            WHERE updated_at < ?
        ''', (cutoff_date,)).fetchone()['count']
        
        if old_conversations > 0:
            # Delete messages first (foreign key constraint)
            conn.execute('''
                DELETE FROM messages 
                WHERE conversation_id IN (
                    SELECT id FROM conversations WHERE updated_at < ?
                )
            ''', (cutoff_date,))
            
            # Delete feedback
            conn.execute('''
                DELETE FROM feedback 
                WHERE conversation_id IN (
                    SELECT id FROM conversations WHERE updated_at < ?
                )
            ''', (cutoff_date,))
            
            # Delete conversations
            conn.execute('''
                DELETE FROM conversations WHERE updated_at < ?
            ''', (cutoff_date,))
            
            conn.commit()
            logger.info(f"🧹 Cleaned up {old_conversations} old conversations")
            
            return jsonify({
                'success': True,
                'message': f'Cleaned up {old_conversations} conversations older than 90 days'
            }), 200
        else:
            return jsonify({
                'success': True,
                'message': 'No old conversations to clean up'
            }), 200
            
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        return jsonify({'error': 'Cleanup failed'}), 500
    finally:
        if conn is not None:
            return_db_connection(conn)
def schedule_database_cleanup():
    """Schedule automatic database cleanup every 24 hours using threading"""
    def cleanup_task():
        try:
            logger.info("🕒 Running scheduled database cleanup...")
            cutoff_date = (datetime.now() - timedelta(days=90)).isoformat()
            
            # Ensure we have app context for database operations
            with app.app_context():
                conn = get_db_connection()
                try:
                    # Get count before cleanup
                    old_count = conn.execute('''
                        SELECT COUNT(*) as count FROM conversations 
                        WHERE updated_at < ?
                    ''', (cutoff_date,)).fetchone()['count']
                    
                    if old_count > 0:
                        # Delete in order: messages, feedback, then conversations
                        conn.execute('''
                            DELETE FROM messages 
                            WHERE conversation_id IN (
                                SELECT id FROM conversations WHERE updated_at < ?
                            )
                        ''', (cutoff_date,))
                        
                        conn.execute('''
                            DELETE FROM feedback 
                            WHERE conversation_id IN (
                                SELECT id FROM conversations WHERE updated_at < ?
                            )
                        ''', (cutoff_date,))
                        
                        conn.execute('''
                            DELETE FROM conversations WHERE updated_at < ?
                        ''', (cutoff_date,))
                        
                        conn.commit()
                        logger.info(f"🧹 Auto-cleaned {old_count} conversations older than 90 days")
                    else:
                        logger.info("🧹 No old conversations to clean up")
                        
                finally:
                    return_db_connection(conn)
                
        except Exception as e:
            logger.error(f"Scheduled cleanup error: {e}")
        finally:
            # Schedule next cleanup in 24 hours
            threading.Timer(24 * 60 * 60, cleanup_task).start()
    
    # Start the cleanup cycle
    cleanup_task()
    
    logger.info("🕒 Database cleanup scheduler started (runs every 24 hours)")
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        conn = get_db_connection()
        conn.execute('SELECT 1')
        return_db_connection(conn)
        
        # Check brain status
        brain_status = companion_brain.get_agi_status()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'brain': {
                'agi_enabled': brain_status.get('agi_enabled', False),
                'session_id': companion_brain.brain.session_id[:8]
            },
            'version': '1.0.0'
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500

# ============================================================================
# Server Initialization
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("🚀 Companion Chat Backend with BaaS")
    print("=" * 70)
    print("✅ Initializing database...")
    init_db()
    init_db_pool(DATABASE)

    print("✅ Companion Brain ready!")
    print(f"   Session ID: {companion_brain.brain.session_id[:8]}...")
    print(f"   App Type: {companion_brain.app_type}")

    # Allow overriding host/port via environment to avoid conflicts (e.g., mobile testing)
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))

    print("\n📊 Server Configuration:")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print("   Debug: True")

    print("\n🧠 BaaS Features:")
    print("   • Intelligent caching")
    print("   • Multi-provider AI (OpenRouter, Groq, HuggingFace, Ollama)")
    print("   • Web search integration")
    print("   • Context management")
    print("   • Automatic fallbacks")

    print("\n🎉 Ready to serve requests!")
    print("=" * 70)

    # Start database cleanup scheduler within app context
    with app.app_context():
        schedule_database_cleanup()

    # Disable the reloader to prevent double-start and port conflicts
    app.run(host=host, port=port, debug=True, use_reloader=False)
