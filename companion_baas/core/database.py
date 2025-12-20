#!/usr/bin/env python3
"""
Database module for Companion AI
Handles conversation persistence and user data
"""

import sqlite3
import json
from typing import List, Dict, Optional
from datetime import datetime, timezone
import os

class Database:
    def __init__(self, db_path: str = "companion.db"):
        # Use test database if running tests
        if "pytest" in os.environ.get("_", ""):
            db_path = ":memory:"
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Conversations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # Messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    agent TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            ''')
            
            # Users table (for future use)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            
            conn.commit()

    def create_conversation(self, conversation_id: str, title: str = "New Chat") -> Dict:
        """Create a new conversation"""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conversation_id, title, now, now)
            )
            conn.commit()
        
        return {
            "id": conversation_id,
            "title": title,
            "messages": [],
            "created_at": now,
            "updated_at": now
        }

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get a conversation with its messages"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get conversation
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            conv_row = cursor.fetchone()
            if not conv_row:
                return None
            
            # Get messages
            cursor.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp",
                (conversation_id,)
            )
            message_rows = cursor.fetchall()
            
            messages = []
            for row in message_rows:
                messages.append({
                    "id": row[0],
                    "conversation_id": row[1],
                    "role": row[2],
                    "type": row[3],
                    "content": row[4],
                    "agent": row[5],
                    "timestamp": row[6]
                })
            
            return {
                "id": conv_row[0],
                "title": conv_row[1],
                "messages": messages,
                "created_at": conv_row[2],
                "updated_at": conv_row[3]
            }

    def get_all_conversations(self) -> List[Dict]:
        """Get all conversations (summary)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id) as message_count "
                "FROM conversations c LEFT JOIN messages m ON c.id = m.conversation_id "
                "GROUP BY c.id ORDER BY c.updated_at DESC"
            )
            rows = cursor.fetchall()
            
            conversations = []
            for row in rows:
                conversations.append({
                    "id": row[0],
                    "title": row[1],
                    "created_at": row[2],
                    "updated_at": row[3],
                    "message_count": row[4]
                })
            
            return conversations

    def add_message(self, conversation_id: str, message: Dict):
        """Add a message to a conversation"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (id, conversation_id, role, type, content, agent, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    message["id"],
                    conversation_id,
                    message["role"],
                    message["type"],
                    message["content"],
                    message.get("agent"),
                    message["timestamp"]
                )
            )
            
            # Update conversation updated_at
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id)
            )
            
            conn.commit()

    def delete_conversation(self, conversation_id: str):
        """Delete a conversation and its messages"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()

# Global database instance
db = Database()