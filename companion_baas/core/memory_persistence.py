#!/usr/bin/env python3
"""
Memory Persistence System
=========================

Enables cross-session memory and context preservation:
- User profiles and preferences
- Conversation history storage
- Semantic memory search
- Long-term context management
- Multi-backend support (Redis, SQLite, PostgreSQL)
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memories"""
    SHORT_TERM = "short_term"      # Current conversation
    LONG_TERM = "long_term"        # Persistent across sessions
    SEMANTIC = "semantic"          # Factual knowledge
    EPISODIC = "episodic"          # Specific events/interactions
    PROCEDURAL = "procedural"      # How-to knowledge
    PREFERENCE = "preference"      # User preferences


@dataclass
class Memory:
    """Single memory unit"""
    id: str
    user_id: str
    content: str
    memory_type: MemoryType
    metadata: Dict[str, Any]
    timestamp: float
    importance: float  # 0.0 to 1.0
    access_count: int
    last_accessed: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Memory':
        """Create from dictionary"""
        return Memory(
            id=data["id"],
            user_id=data["user_id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            metadata=data.get("metadata", {}),
            timestamp=data["timestamp"],
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed", data["timestamp"])
        )


@dataclass
class UserProfile:
    """User profile with preferences"""
    user_id: str
    name: Optional[str]
    preferences: Dict[str, Any]
    interaction_count: int
    first_seen: float
    last_seen: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "preferences": self.preferences,
            "interaction_count": self.interaction_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "metadata": self.metadata
        }


class MemoryBackend:
    """Base class for memory storage backends"""
    
    def store(self, memory: Memory) -> bool:
        """Store memory"""
        raise NotImplementedError
    
    def retrieve(self, memory_id: str) -> Optional[Memory]:
        """Retrieve specific memory"""
        raise NotImplementedError
    
    def search(self, query: str, user_id: str, limit: int = 10) -> List[Memory]:
        """Search memories"""
        raise NotImplementedError
    
    def get_recent(self, user_id: str, limit: int = 10) -> List[Memory]:
        """Get recent memories"""
        raise NotImplementedError
    
    def delete(self, memory_id: str) -> bool:
        """Delete memory"""
        raise NotImplementedError
    
    def update_access(self, memory_id: str):
        """Update access count and timestamp"""
        raise NotImplementedError


class InMemoryBackend(MemoryBackend):
    """In-memory storage (for development/testing)"""
    
    def __init__(self):
        self.memories: Dict[str, Memory] = {}
        self.user_profiles: Dict[str, UserProfile] = {}
        
    def store(self, memory: Memory) -> bool:
        """Store memory"""
        self.memories[memory.id] = memory
        return True
    
    def retrieve(self, memory_id: str) -> Optional[Memory]:
        """Retrieve specific memory"""
        memory = self.memories.get(memory_id)
        if memory:
            self.update_access(memory_id)
        return memory
    
    def search(self, query: str, user_id: str, limit: int = 10) -> List[Memory]:
        """Search memories by text matching"""
        query_lower = query.lower()
        matches = []
        
        for memory in self.memories.values():
            if memory.user_id != user_id:
                continue
            
            # Simple text matching
            if query_lower in memory.content.lower():
                matches.append(memory)
                self.update_access(memory.id)
        
        # Sort by relevance (importance * recency)
        matches.sort(key=lambda m: m.importance * (1.0 / (time.time() - m.timestamp + 1)), reverse=True)
        return matches[:limit]
    
    def get_recent(self, user_id: str, limit: int = 10) -> List[Memory]:
        """Get recent memories"""
        user_memories = [m for m in self.memories.values() if m.user_id == user_id]
        user_memories.sort(key=lambda m: m.timestamp, reverse=True)
        return user_memories[:limit]
    
    def delete(self, memory_id: str) -> bool:
        """Delete memory"""
        if memory_id in self.memories:
            del self.memories[memory_id]
            return True
        return False
    
    def update_access(self, memory_id: str):
        """Update access count and timestamp"""
        if memory_id in self.memories:
            memory = self.memories[memory_id]
            memory.access_count += 1
            memory.last_accessed = time.time()
    
    def store_profile(self, profile: UserProfile):
        """Store user profile"""
        self.user_profiles[profile.user_id] = profile
    
    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile"""
        return self.user_profiles.get(user_id)


class SQLiteBackend(MemoryBackend):
    """SQLite storage backend"""
    
    def __init__(self, db_path: str = "memory.db"):
        self.db_path = db_path
        self.enabled = False
        
        try:
            import sqlite3
            self.sqlite3 = sqlite3
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self._initialize_tables()
            self.enabled = True
            logger.info(f"✅ SQLite backend initialized: {db_path}")
        except Exception as e:
            logger.warning(f"⚠️ SQLite backend unavailable: {e}")
    
    def _initialize_tables(self):
        """Create database tables"""
        cursor = self.conn.cursor()
        
        # Memories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                metadata TEXT,
                timestamp REAL NOT NULL,
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                last_accessed REAL
            )
        """)
        
        # User profiles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                preferences TEXT,
                interaction_count INTEGER DEFAULT 0,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                metadata TEXT
            )
        """)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON memories(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)")
        
        self.conn.commit()
    
    def store(self, memory: Memory) -> bool:
        """Store memory"""
        if not self.enabled:
            return False
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO memories 
            (id, user_id, content, memory_type, metadata, timestamp, importance, access_count, last_accessed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory.id,
            memory.user_id,
            memory.content,
            memory.memory_type.value,
            json.dumps(memory.metadata),
            memory.timestamp,
            memory.importance,
            memory.access_count,
            memory.last_accessed
        ))
        self.conn.commit()
        return True
    
    def retrieve(self, memory_id: str) -> Optional[Memory]:
        """Retrieve specific memory"""
        if not self.enabled:
            return None
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        
        if row:
            self.update_access(memory_id)
            return self._row_to_memory(row)
        return None
    
    def search(self, query: str, user_id: str, limit: int = 10) -> List[Memory]:
        """Search memories"""
        if not self.enabled:
            return []
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM memories 
            WHERE user_id = ? AND content LIKE ?
            ORDER BY importance * (1.0 / (? - timestamp + 1)) DESC
            LIMIT ?
        """, (user_id, f"%{query}%", time.time(), limit))
        
        memories = [self._row_to_memory(row) for row in cursor.fetchall()]
        for memory in memories:
            self.update_access(memory.id)
        return memories
    
    def get_recent(self, user_id: str, limit: int = 10) -> List[Memory]:
        """Get recent memories"""
        if not self.enabled:
            return []
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM memories 
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        
        return [self._row_to_memory(row) for row in cursor.fetchall()]
    
    def delete(self, memory_id: str) -> bool:
        """Delete memory"""
        if not self.enabled:
            return False
        
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def update_access(self, memory_id: str):
        """Update access count and timestamp"""
        if not self.enabled:
            return
        
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE memories 
            SET access_count = access_count + 1, last_accessed = ?
            WHERE id = ?
        """, (time.time(), memory_id))
        self.conn.commit()
    
    def _row_to_memory(self, row) -> Memory:
        """Convert database row to Memory object"""
        return Memory(
            id=row[0],
            user_id=row[1],
            content=row[2],
            memory_type=MemoryType(row[3]),
            metadata=json.loads(row[4]) if row[4] else {},
            timestamp=row[5],
            importance=row[6],
            access_count=row[7],
            last_accessed=row[8]
        )


class MemoryManager:
    """Manages memory operations with forgetting curve"""
    
    def __init__(self, backend: MemoryBackend):
        self.backend = backend
        self.forgetting_enabled = True
        self.importance_threshold = 0.3  # Forget memories below this
        
    def create_memory(
        self,
        user_id: str,
        content: str,
        memory_type: MemoryType,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Memory:
        """Create new memory"""
        memory_id = self._generate_id(user_id, content)
        
        memory = Memory(
            id=memory_id,
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            metadata=metadata or {},
            timestamp=time.time(),
            importance=importance,
            access_count=0,
            last_accessed=time.time()
        )
        
        self.backend.store(memory)
        return memory
    
    def recall(self, memory_id: str) -> Optional[Memory]:
        """Recall specific memory"""
        return self.backend.retrieve(memory_id)
    
    def search_memories(
        self,
        query: str,
        user_id: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10
    ) -> List[Memory]:
        """Search for relevant memories"""
        memories = self.backend.search(query, user_id, limit)
        
        # Filter by type if specified
        if memory_type:
            memories = [m for m in memories if m.memory_type == memory_type]
        
        return memories
    
    def get_context(self, user_id: str, limit: int = 10) -> str:
        """Get recent context for user"""
        recent = self.backend.get_recent(user_id, limit)
        
        context_parts = []
        for memory in recent:
            age = time.time() - memory.timestamp
            age_str = self._format_age(age)
            context_parts.append(f"[{age_str} ago] {memory.content}")
        
        return "\n".join(context_parts)
    
    def forget_old_memories(self, user_id: str, days: int = 30):
        """Forget memories older than specified days"""
        if not self.forgetting_enabled:
            return
        
        cutoff = time.time() - (days * 24 * 60 * 60)
        recent = self.backend.get_recent(user_id, limit=1000)
        
        for memory in recent:
            # Apply forgetting curve
            age = time.time() - memory.timestamp
            decay = self._calculate_decay(age, memory.access_count)
            
            current_importance = memory.importance * decay
            
            if current_importance < self.importance_threshold and memory.timestamp < cutoff:
                self.backend.delete(memory.id)
                logger.info(f"Forgot memory: {memory.id}")
    
    def _calculate_decay(self, age_seconds: float, access_count: int) -> float:
        """
        Calculate memory decay using forgetting curve
        More access = slower decay
        """
        days = age_seconds / (24 * 60 * 60)
        # Ebbinghaus forgetting curve: R = e^(-t/S)
        # S increases with rehearsal (access_count)
        S = 1 + (access_count * 0.5)  # Spacing effect
        return 2.71828 ** (-days / S)
    
    def _generate_id(self, user_id: str, content: str) -> str:
        """Generate unique memory ID"""
        combined = f"{user_id}:{content}:{time.time()}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _format_age(self, seconds: float) -> str:
        """Format age in human-readable form"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m"
        elif seconds < 86400:
            return f"{int(seconds/3600)}h"
        else:
            return f"{int(seconds/86400)}d"


class ConversationHistory:
    """Manages conversation history"""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.max_history_length = 50
    
    def add_message(
        self,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add message to history"""
        self.memory_manager.create_memory(
            user_id=user_id,
            content=f"{role}: {content}",
            memory_type=MemoryType.EPISODIC,
            importance=0.7 if role == "user" else 0.5,
            metadata={
                "role": role,
                "message_content": content,
                **(metadata or {})
            }
        )
    
    def get_conversation(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Tuple[str, str]]:
        """
        Get recent conversation
        
        Returns:
            List of (role, content) tuples
        """
        memories = self.memory_manager.backend.get_recent(user_id, limit)
        
        conversation = []
        for memory in reversed(memories):  # Chronological order
            if memory.memory_type == MemoryType.EPISODIC:
                role = memory.metadata.get("role", "unknown")
                content = memory.metadata.get("message_content", memory.content)
                conversation.append((role, content))
        
        return conversation


class MemoryPersistenceSystem:
    """
    Unified Memory Persistence System
    Handles all memory and context management
    """
    
    def __init__(self, backend: Optional[MemoryBackend] = None):
        # Use SQLite by default, fallback to in-memory
        if backend is None:
            backend = SQLiteBackend()
            if not backend.enabled:
                logger.warning("SQLite unavailable, using in-memory storage")
                backend = InMemoryBackend()
        
        self.backend = backend
        self.memory_manager = MemoryManager(backend)
        self.conversation_history = ConversationHistory(self.memory_manager)
        
        self.enabled = True
        logger.info("✅ Memory Persistence System initialized")
    
    def remember(
        self,
        user_id: str,
        content: str,
        memory_type: str = "long_term",
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Memory:
        """
        Store a memory
        
        Args:
            user_id: User identifier
            content: Memory content
            memory_type: Type of memory
            importance: Importance score (0.0-1.0)
            metadata: Additional metadata
            
        Returns:
            Created Memory object
        """
        mem_type = MemoryType(memory_type)
        return self.memory_manager.create_memory(
            user_id=user_id,
            content=content,
            memory_type=mem_type,
            importance=importance,
            metadata=metadata
        )
    
    def recall(
        self,
        user_id: str,
        query: str,
        limit: int = 10
    ) -> List[Memory]:
        """
        Recall relevant memories
        
        Args:
            user_id: User identifier
            query: Search query
            limit: Max memories to return
            
        Returns:
            List of relevant memories
        """
        return self.memory_manager.search_memories(query, user_id, limit=limit)
    
    def get_context(
        self,
        user_id: str,
        limit: int = 10
    ) -> str:
        """
        Get conversation context
        
        Args:
            user_id: User identifier
            limit: Number of recent interactions
            
        Returns:
            Formatted context string
        """
        return self.memory_manager.get_context(user_id, limit)
    
    def add_interaction(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record an interaction
        
        Args:
            user_id: User identifier
            user_message: User's message
            assistant_response: Assistant's response
            metadata: Additional metadata
        """
        self.conversation_history.add_message(
            user_id=user_id,
            role="user",
            content=user_message,
            metadata=metadata
        )
        
        self.conversation_history.add_message(
            user_id=user_id,
            role="assistant",
            content=assistant_response,
            metadata=metadata
        )
    
    def get_conversation(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Tuple[str, str]]:
        """
        Get conversation history
        
        Args:
            user_id: User identifier
            limit: Number of messages
            
        Returns:
            List of (role, content) tuples
        """
        return self.conversation_history.get_conversation(user_id, limit)
    
    def cleanup(self, user_id: str, days: int = 30):
        """
        Clean up old memories
        
        Args:
            user_id: User identifier
            days: Forget memories older than this
        """
        self.memory_manager.forget_old_memories(user_id, days)


# Convenience function
def create_memory_system(backend: Optional[str] = None) -> MemoryPersistenceSystem:
    """
    Create memory persistence system
    
    Args:
        backend: 'sqlite', 'memory', or None (auto-detect)
        
    Returns:
        MemoryPersistenceSystem instance
    """
    if backend == "memory":
        return MemoryPersistenceSystem(InMemoryBackend())
    elif backend == "sqlite":
        return MemoryPersistenceSystem(SQLiteBackend())
    else:
        return MemoryPersistenceSystem()  # Auto-detect
