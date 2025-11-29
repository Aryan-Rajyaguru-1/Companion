#!/usr/bin/env python3
"""
Authentication Backend for Companion AI
Handles user registration, login, and session management
"""

import sqlite3
import hashlib
import secrets
import jwt
import time
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class AuthManager:
    """Authentication and user management system"""
    
    def __init__(self, db_path: str = "auth.db"):
        self.db_path = db_path
        self.jwt_secret = self._get_or_create_secret()
        self.setup_database()
    
    def _get_or_create_secret(self) -> str:
        """Get or create JWT secret key"""
        try:
            with open('.jwt_secret', 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            secret = secrets.token_hex(32)
            with open('.jwt_secret', 'w') as f:
                f.write(secret)
            return secret
    
    def setup_database(self):
        """Initialize the authentication database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_verified BOOLEAN DEFAULT FALSE,
                verification_token TEXT,
                reset_token TEXT,
                reset_token_expires TIMESTAMP,
                newsletter_subscribed BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Sessions table for tracking active sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                token_hash TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                user_agent TEXT,
                ip_address TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Login attempts table for security
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("🔐 Authentication database initialized")
    
    def _hash_password(self, password: str, salt: str = None) -> Tuple[str, str]:
        """Hash password with salt"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        # Use PBKDF2 for secure password hashing
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # iterations
        )
        
        return password_hash.hex(), salt
    
    def _verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        """Verify password against stored hash"""
        password_hash, _ = self._hash_password(password, salt)
        return password_hash == stored_hash
    
    def _generate_jwt_token(self, user_id: int, email: str, remember: bool = False) -> str:
        """Generate JWT token for user"""
        expiry_hours = 30 * 24 if remember else 24  # 30 days if remember, 1 day otherwise
        
        payload = {
            'user_id': user_id,
            'email': email,
            'exp': datetime.utcnow() + timedelta(hours=expiry_hours),
            'iat': datetime.utcnow(),
            'remember': remember
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    
    def verify_jwt_token(self, token: str) -> Optional[Dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid JWT token")
            return None
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _validate_password(self, password: str) -> Tuple[bool, str]:
        """Validate password strength"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        
        return True, "Password is valid"
    
    def _check_rate_limit(self, email: str, ip_address: str) -> bool:
        """Check if user/IP is rate limited"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check failed attempts in last 15 minutes
        cursor.execute('''
            SELECT COUNT(*) FROM login_attempts 
            WHERE (email = ? OR ip_address = ?) 
            AND success = FALSE 
            AND attempted_at > datetime('now', '-15 minutes')
        ''', (email, ip_address))
        
        failed_attempts = cursor.fetchone()[0]
        conn.close()
        
        return failed_attempts < 5  # Allow 5 failed attempts per 15 minutes
    
    def _log_login_attempt(self, email: str, ip_address: str, success: bool):
        """Log login attempt for security monitoring"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO login_attempts (email, ip_address, success)
            VALUES (?, ?, ?)
        ''', (email, ip_address, success))
        
        conn.commit()
        conn.close()
    
    def register_user(self, email: str, name: str, password: str, newsletter: bool = False) -> Tuple[bool, str, Optional[Dict]]:
        """Register a new user"""
        # Validate input
        if not self._validate_email(email):
            return False, "Invalid email format", None
        
        is_valid, password_message = self._validate_password(password)
        if not is_valid:
            return False, password_message, None
        
        if len(name.strip()) < 2:
            return False, "Name must be at least 2 characters long", None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if user already exists
            cursor.execute('SELECT id FROM users WHERE email = ?', (email.lower(),))
            if cursor.fetchone():
                return False, "Email address already registered", None
            
            # Hash password
            password_hash, salt = self._hash_password(password)
            
            # Generate verification token
            verification_token = secrets.token_urlsafe(32)
            
            # Insert user
            cursor.execute('''
                INSERT INTO users (email, name, password_hash, salt, verification_token, newsletter_subscribed)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (email.lower(), name.strip(), password_hash, salt, verification_token, newsletter))
            
            user_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"✅ User registered: {email}")
            
            return True, "Registration successful", {
                'user_id': user_id,
                'email': email,
                'name': name,
                'verification_token': verification_token
            }
            
        except sqlite3.Error as e:
            logger.error(f"Database error during registration: {e}")
            return False, "Registration failed due to database error", None
        finally:
            conn.close()
    
    def login_user(self, email: str, password: str, ip_address: str = "", user_agent: str = "", remember: bool = False) -> Tuple[bool, str, Optional[Dict]]:
        """Authenticate user login"""
        # Check rate limiting
        if not self._check_rate_limit(email, ip_address):
            self._log_login_attempt(email, ip_address, False)
            return False, "Too many failed attempts. Please try again later.", None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get user data
            cursor.execute('''
                SELECT id, email, name, password_hash, salt, is_active, is_verified
                FROM users WHERE email = ?
            ''', (email.lower(),))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                self._log_login_attempt(email, ip_address, False)
                return False, "Invalid email or password", None
            
            user_id, user_email, name, stored_hash, salt, is_active, is_verified = user_data
            
            # Check if account is active
            if not is_active:
                self._log_login_attempt(email, ip_address, False)
                return False, "Account is deactivated", None
            
            # Verify password
            if not self._verify_password(password, stored_hash, salt):
                self._log_login_attempt(email, ip_address, False)
                return False, "Invalid email or password", None
            
            # Update last login
            cursor.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
            ''', (user_id,))
            
            # Generate JWT token
            token = self._generate_jwt_token(user_id, user_email, remember)
            
            # Store session
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expires_at = datetime.utcnow() + timedelta(days=30 if remember else 1)
            
            cursor.execute('''
                INSERT INTO sessions (user_id, token_hash, expires_at, user_agent, ip_address)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, token_hash, expires_at, user_agent, ip_address))
            
            conn.commit()
            
            self._log_login_attempt(email, ip_address, True)
            logger.info(f"✅ User logged in: {email}")
            
            return True, "Login successful", {
                'token': token,
                'user': {
                    'id': user_id,
                    'email': user_email,
                    'name': name,
                    'is_verified': bool(is_verified)
                }
            }
            
        except sqlite3.Error as e:
            logger.error(f"Database error during login: {e}")
            return False, "Login failed due to database error", None
        finally:
            conn.close()
    
    def logout_user(self, token: str) -> bool:
        """Logout user by invalidating token"""
        try:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE sessions SET is_active = FALSE WHERE token_hash = ?
            ''', (token_hash,))
            
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            return False
    
    def get_user_by_token(self, token: str) -> Optional[Dict]:
        """Get user information from valid token"""
        payload = self.verify_jwt_token(token)
        if not payload:
            return None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Verify session is still active
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            cursor.execute('''
                SELECT s.is_active, u.id, u.email, u.name, u.is_verified
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token_hash = ? AND s.expires_at > CURRENT_TIMESTAMP
            ''', (token_hash,))
            
            result = cursor.fetchone()
            
            if not result or not result[0]:  # Session not found or not active
                return None
            
            _, user_id, email, name, is_verified = result
            
            return {
                'id': user_id,
                'email': email,
                'name': name,
                'is_verified': bool(is_verified)
            }
            
        except sqlite3.Error as e:
            logger.error(f"Database error during token verification: {e}")
            return None
        finally:
            conn.close()
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
        """Change user password"""
        is_valid, password_message = self._validate_password(new_password)
        if not is_valid:
            return False, password_message
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get current password
            cursor.execute('SELECT password_hash, salt FROM users WHERE id = ?', (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return False, "User not found"
            
            stored_hash, salt = result
            
            # Verify old password
            if not self._verify_password(old_password, stored_hash, salt):
                return False, "Current password is incorrect"
            
            # Hash new password
            new_hash, new_salt = self._hash_password(new_password)
            
            # Update password
            cursor.execute('''
                UPDATE users SET password_hash = ?, salt = ? WHERE id = ?
            ''', (new_hash, new_salt, user_id))
            
            # Invalidate all sessions except current one
            cursor.execute('''
                UPDATE sessions SET is_active = FALSE WHERE user_id = ?
            ''', (user_id,))
            
            conn.commit()
            
            logger.info(f"✅ Password changed for user ID: {user_id}")
            return True, "Password changed successfully"
            
        except sqlite3.Error as e:
            logger.error(f"Database error during password change: {e}")
            return False, "Password change failed"
        finally:
            conn.close()
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions and tokens"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Remove expired sessions
            cursor.execute('''
                DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP
            ''')
            
            # Remove old login attempts (older than 7 days)
            cursor.execute('''
                DELETE FROM login_attempts WHERE attempted_at < datetime('now', '-7 days')
            ''')
            
            conn.commit()
            logger.info("🧹 Cleaned up expired sessions and old login attempts")
            
        except sqlite3.Error as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            conn.close()
    
    def get_user_stats(self) -> Dict:
        """Get authentication system statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Total users
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            # Active users (logged in last 30 days)
            cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE last_login > datetime('now', '-30 days')
            ''')
            active_users = cursor.fetchone()[0]
            
            # Verified users
            cursor.execute('SELECT COUNT(*) FROM users WHERE is_verified = TRUE')
            verified_users = cursor.fetchone()[0]
            
            # Active sessions
            cursor.execute('''
                SELECT COUNT(*) FROM sessions 
                WHERE is_active = TRUE AND expires_at > CURRENT_TIMESTAMP
            ''')
            active_sessions = cursor.fetchone()[0]
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'verified_users': verified_users,
                'active_sessions': active_sessions
            }
            
        except sqlite3.Error as e:
            logger.error(f"Error getting stats: {e}")
            return {}
        finally:
            conn.close()

# Global auth manager instance
auth_manager = AuthManager()

if __name__ == "__main__":
    # Test the authentication system
    logging.basicConfig(level=logging.INFO)
    
    print("🔐 Authentication System Test")
    print("=" * 40)
    
    # Test registration
    success, message, data = auth_manager.register_user(
        "test@example.com", 
        "Test User", 
        "TestPassword123!", 
        newsletter=True
    )
    print(f"Registration: {success} - {message}")
    
    if success:
        # Test login
        success, message, data = auth_manager.login_user(
            "test@example.com", 
            "TestPassword123!", 
            "127.0.0.1", 
            "Test Agent"
        )
        print(f"Login: {success} - {message}")
        
        if success:
            token = data['token']
            print(f"Token: {token[:50]}...")
            
            # Test token verification
            user = auth_manager.get_user_by_token(token)
            print(f"User from token: {user}")
    
    # Get stats
    stats = auth_manager.get_user_stats()
    print(f"Stats: {stats}")
