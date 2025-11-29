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
import json
import os
import sys
import uuid
from datetime import datetime, timedelta
import sqlite3
import logging

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
    enable_agi=True,          # ✨ NEW: Enable AGI features (personality, reasoning, learning)
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

# Configure logging
logging.basicConfig(level=logging.INFO)

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
    conn.close()

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def generate_chat_title(message):
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
        email = data.get('email', '').strip().lower()
        name = data.get('name', '').strip()
        password = data.get('password', '')
        newsletter = data.get('newsletter', False)
        
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
                'user': {
                    'id': user_data['user_id'],
                    'email': email,
                    'name': name
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
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        remember = data.get('remember', False)
        
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
                'token': auth_data['token'],
                'user': auth_data['user']
            }), 200
        else:
            return jsonify({'success': False, 'message': message}), 401
            
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
            return jsonify({'success': True, 'message': 'Logged out successfully'}), 200
        else:
            return jsonify({'success': False, 'message': 'Logout failed'}), 500
            
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
        return jsonify({'success': True, 'user': request.current_user}), 200
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
        conn.close()
        
        return jsonify({
            'id': conversation_id,
            'title': title,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
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
        
        logger.info(f"📨 Message to conversation {conversation_id}: {message[:50]}...")
        logger.info(f"🔧 Tools: {active_tools}")
        
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        conn = get_db_connection()
        
        # Check if conversation exists
        conv = conn.execute(
            'SELECT id, title FROM conversations WHERE id = ?',
            (conversation_id,)
        ).fetchone()
        
        if not conv:
            conn.close()
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Save user message
        user_msg_id = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO messages (id, conversation_id, role, content)
            VALUES (?, ?, ?, ?)
        ''', (user_msg_id, conversation_id, 'user', message))
        conn.commit()
        
        # ====================================================================
        # 🧠 USE COMPANION BRAIN - This replaces 2000+ lines of AI logic!
        # ====================================================================
        brain_response = companion_brain.chat(
            message=message,
            conversation_id=conversation_id,
            tools=active_tools
        )
        
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
        conn.close()
        
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
    
    except Exception as e:
        logger.error(f"❌ Error in send_message: {e}", exc_info=True)
        return jsonify({'error': f'Failed to process message: {str(e)}'}), 500

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
        conn.close()
        
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
# KEEP: Static file serving
# ============================================================================

@app.route('/')
def serve_index():
    """Serve the main HTML file"""
    return send_from_directory('.', 'modern-demo.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('.', path)

# ============================================================================
# Server Initialization
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("🚀 Companion Chat Backend with BaaS")
    print("=" * 70)
    print("✅ Initializing database...")
    init_db()
    
    print("✅ Companion Brain ready!")
    print(f"   Session ID: {companion_brain.brain.session_id[:8]}...")
    print(f"   App Type: {companion_brain.app_type}")
    
    print("\n📊 Server Configuration:")
    print("   Host: 0.0.0.0")
    print("   Port: 5000")
    print("   Debug: True")
    
    print("\n🧠 BaaS Features:")
    print("   • Intelligent caching")
    print("   • Multi-provider AI (OpenRouter, Groq, HuggingFace, Ollama)")
    print("   • Web search integration")
    print("   • Context management")
    print("   • Automatic fallbacks")
    
    print("\n🎉 Ready to serve requests!")
    print("=" * 70)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
