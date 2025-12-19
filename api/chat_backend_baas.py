#!/usr/bin/env python3
"""
Simplified Companion AI API for Vercel Deployment
Standalone version without companion_baas dependencies
"""

import sqlite3
import hashlib
import secrets
import jwt
import time
import re
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
import logging
import uuid

logger = logging.getLogger(__name__)

# ============================================================================
# AUTHENTICATION MANAGER
# ============================================================================

class AuthManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # For Vercel, use /tmp directory for writable storage
            if os.environ.get('VERCEL_ENV') or os.environ.get('VERCEL'):
                import tempfile
                temp_dir = tempfile.gettempdir()
                db_path = os.path.join(temp_dir, 'auth.db')
            else:
                db_path = os.path.join(os.path.dirname(__file__), 'auth.db')
        self.db_path = db_path
        self.jwt_secret = self._get_or_create_secret()
        # Don't initialize database at import time for Vercel
        if not (os.environ.get('VERCEL_ENV') or os.environ.get('VERCEL')):
            self.setup_database()

    def _get_or_create_secret(self) -> str:
        """Get or create JWT secret key"""
        secret = os.environ.get('JWT_SECRET')
        if secret:
            return secret
        # For Vercel, always use environment variable
        return secrets.token_hex(32)

    def _ensure_database(self):
        """Ensure database is initialized before use"""
        if not hasattr(self, '_db_initialized'):
            self.setup_database()
            self._db_initialized = True

    def setup_database(self):
        """Initialize SQLite database"""
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                newsletter BOOLEAN DEFAULT FALSE
            )
        ''')

        # Create sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash)')

        conn.commit()
        conn.close()
        logger.info("🔐 Authentication database initialized")

    def _hash_password(self, password: str, salt: str = None) -> Tuple[str, str]:
        """Hash password with salt using PBKDF2"""
        if salt is None:
            salt = secrets.token_hex(16)

        # Use PBKDF2 for secure password hashing
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        password_hash = hash_obj.hex()

        return password_hash, salt

    def register_user(self, email: str, name: str, password: str, newsletter: bool = False) -> Tuple[bool, str, Dict]:
        """Register a new user"""
        self._ensure_database()
        try:
            # Validate input
            if not email or not name or not password:
                return False, "All fields are required", {}

            if len(password) < 8:
                return False, "Password must be at least 8 characters", {}

            # Hash password
            password_hash, salt = self._hash_password(password)

            # Store user
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO users (email, password_hash, name, newsletter)
                VALUES (?, ?, ?, ?)
            ''', (email, f"{password_hash}:{salt}", name, newsletter))

            user_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Generate token
            token = self._generate_token(user_id, email)

            return True, "User registered successfully", {
                "user": {"id": user_id, "email": email, "name": name},
                "token": token
            }

        except sqlite3.IntegrityError:
            return False, "Email already registered", {}
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False, "Registration failed", {}

    def login_user(self, email: str, password: str) -> Tuple[bool, str, Dict]:
        """Authenticate user login"""
        self._ensure_database()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get user
            cursor.execute('SELECT id, password_hash, name FROM users WHERE email = ?', (email,))
            user = cursor.fetchone()

            if not user:
                return False, "Invalid email or password", {}

            user_id, stored_hash, name = user

            # Verify password
            if ':' in stored_hash:
                password_hash, salt = stored_hash.split(':', 1)
                computed_hash, _ = self._hash_password(password, salt)
            else:
                # Legacy SHA256 support
                computed_hash = hashlib.sha256(password.encode()).hexdigest()
                password_hash = stored_hash

            if computed_hash != password_hash:
                return False, "Invalid email or password", {}

            # Update last login
            cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))

            # Generate token
            token = self._generate_token(user_id, email)

            conn.commit()
            conn.close()

            return True, "Login successful", {
                "user": {"id": user_id, "email": email, "name": name},
                "token": token
            }

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False, "Login failed", {}

    def _generate_token(self, user_id: int, email: str) -> str:
        """Generate JWT token"""
        payload = {
            "user_id": user_id,
            "email": email,
            "exp": int(time.time()) + 86400,  # 24 hours
            "iat": int(time.time())
        }
        token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
        return token

    def get_user_by_token(self, token: str) -> Optional[Dict]:
        """Validate token and return user info"""
        self._ensure_database()
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])

            # Check expiration
            if payload['exp'] < time.time():
                return None

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT id, email, name FROM users WHERE id = ?', (payload['user_id'],))
            user = cursor.fetchone()
            conn.close()

            if user:
                return {"id": user[0], "email": user[1], "name": user[2]}

            return None

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None

    def get_user_stats(self) -> Dict:
        """Get user statistics"""
        self._ensure_database()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM users WHERE last_login > datetime("now", "-7 days")')
            active_users = cursor.fetchone()[0]

            conn.close()

            return {
                "total_users": total_users,
                "active_users": active_users,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {"error": str(e)}

# Initialize auth manager
auth_manager = AuthManager()

# ============================================================================
# SIMPLE CHAT BACKEND
# ============================================================================

class SimpleChatBackend:
    def __init__(self):
        self.api_key = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('GROQ_API_KEY')
        self.model = os.environ.get('MODEL', 'microsoft/wizardlm-2-8x22b')

    def generate_response(self, message: str, user_id: int = None) -> str:
        """Generate a simple AI response"""
        try:
            # For now, return a simple response
            # In a real implementation, you'd call an AI API here
            responses = [
                "Hello! I'm your Companion AI. How can I help you today?",
                "That's an interesting question. Let me think about that.",
                "I'm here to assist you. What would you like to know?",
                "Great question! Here's what I think...",
                "I understand. Let me help you with that.",
            ]

            # Simple keyword-based responses
            message_lower = message.lower()

            if 'hello' in message_lower or 'hi' in message_lower:
                return "Hello! Nice to meet you. I'm your Companion AI assistant."
            elif 'how are you' in message_lower:
                return "I'm doing well, thank you for asking! How are you doing today?"
            elif 'help' in message_lower:
                return "I can help you with various tasks. Just ask me anything!"
            elif 'bye' in message_lower or 'goodbye' in message_lower:
                return "Goodbye! Have a great day!"
            else:
                # Return a random response
                import random
                return random.choice(responses)

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I'm sorry, I encountered an error. Please try again."

# Initialize chat backend
chat_backend = SimpleChatBackend()

# Lazy initialization for auth manager
_auth_manager = None

def get_auth_manager():
    """Get or create auth manager instance"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager

# ============================================================================
# DATABASE SETUP FOR CHAT
# ============================================================================

CHAT_DATABASE = os.path.join(os.path.dirname(__file__), 'chat_history.db')

def init_chat_db():
    """Initialize the chat database"""
    # For Vercel, use /tmp directory
    global CHAT_DATABASE
    if os.environ.get('VERCEL_ENV') or os.environ.get('VERCEL'):
        import tempfile
        temp_dir = tempfile.gettempdir()
        CHAT_DATABASE = os.path.join(temp_dir, 'chat_history.db')
    else:
        CHAT_DATABASE = os.path.join(os.path.dirname(__file__), 'chat_history.db')

    # Ensure the directory exists
    os.makedirs(os.path.dirname(CHAT_DATABASE), exist_ok=True)

    conn = sqlite3.connect(CHAT_DATABASE)
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

    conn.commit()
    conn.close()
    logger.info("💬 Chat database initialized")

# Initialize chat database only when needed
_chat_db_initialized = False

def ensure_chat_db():
    """Ensure chat database is initialized"""
    global _chat_db_initialized
    if not _chat_db_initialized:
        init_chat_db()
        _chat_db_initialized = True

# ============================================================================
# FLASK APPLICATION
# ============================================================================

from flask import Flask, request, jsonify, send_from_directory
# from flask_cors import CORS  # Commented out for Vercel compatibility

app = Flask(__name__)
# CORS(app)  # Commented out for Vercel compatibility

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        email = data.get('email', '').strip()
        name = data.get('name', '').strip()
        password = data.get('password', '')

        success, message, result = get_auth_manager().register_user(email, name, password)

        if success:
            return jsonify({
                "success": True,
                "message": message,
                "data": result
            })
        else:
            return jsonify({"error": message}), 400

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({"error": "Registration failed"}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        email = data.get('email', '').strip()
        password = data.get('password', '')

        success, message, result = get_auth_manager().login_user(email, password)

        if success:
            return jsonify({
                "success": True,
                "message": message,
                "data": result
            })
        else:
            return jsonify({"error": message}), 401

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": "Login failed"}), 500

@app.route('/api/auth/verify', methods=['GET'])
def verify_token():
    """Verify JWT token"""
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "No token provided"}), 401

        token = auth_header.replace('Bearer ', '')
        user = get_auth_manager().get_user_by_token(token)

        if user:
            return jsonify({
                "success": True,
                "user": user
            })
        else:
            return jsonify({"error": "Invalid token"}), 401

    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return jsonify({"error": "Token verification failed"}), 500

@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """Get current authenticated user info"""
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "No token provided"}), 401

        token = auth_header.replace('Bearer ', '')
        user = get_auth_manager().get_user_by_token(token)

        if user:
            return jsonify({
                "success": True,
                "user": user
            })
        else:
            return jsonify({"error": "Invalid token"}), 401

    except Exception as e:
        logger.error(f"Get current user error: {e}")
        return jsonify({"error": "Failed to get user info"}), 500

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get all conversations"""
    ensure_chat_db()
    try:
        conn = sqlite3.connect(CHAT_DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all conversations ordered by most recent
        conversations = cursor.execute('''
            SELECT id, title, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC
        ''').fetchall()

        conn.close()

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
    ensure_chat_db()
    try:
        data = request.get_json() or {}
        title = data.get('title', 'New Chat')

        conn = sqlite3.connect(CHAT_DATABASE)
        cursor = conn.cursor()
        conversation_id = str(uuid.uuid4())

        cursor.execute('''
            INSERT INTO conversations (id, title)
            VALUES (?, ?)
        ''', (conversation_id, title))

        conn.commit()
        conn.close()

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
    ensure_chat_db()
    try:
        conn = sqlite3.connect(CHAT_DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if conversation exists
        conv = cursor.execute(
            'SELECT id FROM conversations WHERE id = ?',
            (conversation_id,)
        ).fetchone()

        if not conv:
            conn.close()
            return jsonify({'error': 'Conversation not found'}), 404

        # Get messages
        messages = cursor.execute('''
            SELECT id, role, content, timestamp, metadata
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        ''', (conversation_id,)).fetchall()

        conn.close()

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
def send_message(conversation_id):
    """Send a message and get AI response"""
    ensure_chat_db()
    try:
        # Verify authentication
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "No token provided"}), 401

        token = auth_header.replace('Bearer ', '')
        user = get_auth_manager().get_user_by_token(token)

        if not user:
            return jsonify({"error": "Invalid token"}), 401

        # Get chat data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        message = data.get('message', '').strip()
        if not message:
            return jsonify({"error": "No message provided"}), 400

        conn = sqlite3.connect(CHAT_DATABASE)
        cursor = conn.cursor()

        # Check if conversation exists
        conv = cursor.execute(
            'SELECT id, title FROM conversations WHERE id = ?',
            (conversation_id,)
        ).fetchone()

        if not conv:
            conn.close()
            return jsonify({'error': 'Conversation not found'}), 404

        # Save user message
        user_msg_id = str(uuid.uuid4())
        utc_now = datetime.utcnow().isoformat() + 'Z'
        cursor.execute('''
            INSERT INTO messages (id, conversation_id, role, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_msg_id, conversation_id, 'user', message, utc_now))

        # Generate AI response
        ai_response = chat_backend.generate_response(message, user['id'])

        # Save AI response
        ai_msg_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO messages (id, conversation_id, role, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (ai_msg_id, conversation_id, 'assistant', ai_response, utc_now))

        # Update conversation title if first message
        message_count = cursor.execute(
            'SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?',
            (conversation_id,)
        ).fetchone()[0]

        if message_count == 2:  # Only the user and AI messages exist
            # Generate title from first message
            title = message.strip()[:50]
            if len(message) > 50:
                title += "..."
            cursor.execute(
                'UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?',
                (title, utc_now, conversation_id)
            )

        conn.commit()
        conn.close()

        # Return response
        return jsonify({
            'user_message': {
                'id': user_msg_id,
                'role': 'user',
                'content': message,
                'timestamp': utc_now
            },
            'assistant_message': {
                'id': ai_msg_id,
                'role': 'assistant',
                'content': ai_response,
                'timestamp': utc_now,
                'metadata': {}
            }
        }), 200

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({"error": "Chat failed"}), 500

@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Delete a conversation and all its messages"""
    ensure_chat_db()
    try:
        conn = sqlite3.connect(CHAT_DATABASE)
        cursor = conn.cursor()

        # Delete messages first
        cursor.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))

        # Delete conversation
        cursor.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))

        conn.commit()
        conn.close()

        logger.info(f"🗑️ Deleted conversation {conversation_id}")
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        return jsonify({'error': 'Failed to delete conversation'}), 500

@app.route('/api/user/stats', methods=['GET'])
def user_stats():
    """Get user statistics"""
    try:
        # Verify authentication
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "No token provided"}), 401

        token = auth_header.replace('Bearer ', '')
        user = get_auth_manager().get_user_by_token(token)

        if not user:
            return jsonify({"error": "Invalid token"}), 401

        # Get stats
        stats = get_auth_manager().get_user_stats()

        return jsonify({
            "success": True,
            "stats": stats
        })

    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": "Failed to get stats"}), 500

# ============================================================================
# STATIC FILE SERVING
# ============================================================================

@app.route('/')
def serve_index():
    """Serve login page"""
    try:
        return send_from_directory('../website/frontend', 'login.html')
    except:
        return send_from_directory('.', 'login.html')

@app.route('/home')
def serve_home():
    """Serve home page"""
    try:
        return send_from_directory('../website/frontend', 'index.html')
    except:
        return send_from_directory('.', 'index.html')

@app.route('/chat')
def serve_chat():
    """Serve chat interface"""
    try:
        return send_from_directory('../website/frontend', 'modern-demo.html')
    except:
        return send_from_directory('.', 'modern-demo.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    try:
        return send_from_directory('../website/frontend', path)
    except:
        try:
            return send_from_directory('.', path)
        except:
            return jsonify({"error": "File not found"}), 404

# ============================================================================
# MAIN APPLICATION
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
