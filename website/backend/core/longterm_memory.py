#!/usr/bin/env python3
"""
Long-term Memory System
=======================

Extended context and memory management:
- Context window management (beyond session)
- Smart summarization
- Context compression
- Memory retrieval strategies
- Hierarchical memory organization
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics
import hashlib

logger = logging.getLogger(__name__)


class MemoryLevel(Enum):
    """Hierarchical memory levels"""
    WORKING = "working"          # Current conversation
    SHORT_TERM = "short_term"    # Recent session
    LONG_TERM = "long_term"      # Persistent knowledge
    CORE = "core"                # Essential facts


class CompressionStrategy(Enum):
    """Context compression strategies"""
    SUMMARIZATION = "summarization"
    EXTRACTION = "extraction"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"


@dataclass
class ContextWindow:
    """Manages a context window"""
    max_tokens: int
    current_tokens: int
    messages: List[Dict[str, Any]]
    compressed: bool = False
    
    def can_fit(self, message_tokens: int) -> bool:
        """Check if message can fit"""
        return (self.current_tokens + message_tokens) <= self.max_tokens
    
    def add_message(self, message: Dict[str, Any], token_count: int):
        """Add message to window"""
        if self.can_fit(token_count):
            self.messages.append(message)
            self.current_tokens += token_count
            return True
        return False
    
    def get_usage_ratio(self) -> float:
        """Get usage ratio (0.0 to 1.0)"""
        return self.current_tokens / self.max_tokens if self.max_tokens > 0 else 0
    
    def clear(self):
        """Clear window"""
        self.messages.clear()
        self.current_tokens = 0
        self.compressed = False


@dataclass
class MemoryNode:
    """Node in hierarchical memory structure"""
    id: str
    level: MemoryLevel
    content: str
    summary: Optional[str]
    children: List[str]  # Child node IDs
    parent: Optional[str]  # Parent node ID
    metadata: Dict[str, Any]
    importance: float  # 0.0 to 1.0
    access_count: int
    created_at: float
    last_accessed: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level.value,
            "content": self.content,
            "summary": self.summary,
            "children": self.children,
            "parent": self.parent,
            "metadata": self.metadata,
            "importance": self.importance,
            "access_count": self.access_count,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed
        }


class TokenCounter:
    """Estimate token counts"""
    
    @staticmethod
    def count_tokens(text: str) -> int:
        """
        Estimate token count
        Simplified: ~4 chars per token average
        """
        return len(text) // 4
    
    @staticmethod
    def count_message_tokens(message: Dict[str, Any]) -> int:
        """Count tokens in a message"""
        total = 0
        for key, value in message.items():
            if isinstance(value, str):
                total += TokenCounter.count_tokens(value)
        return total + 4  # Overhead


class ContextCompressor:
    """Compress context to fit in window"""
    
    def __init__(self, llm_function):
        self.llm_function = llm_function
    
    def compress_messages(
        self,
        messages: List[Dict[str, Any]],
        target_tokens: int,
        strategy: CompressionStrategy = CompressionStrategy.SUMMARIZATION
    ) -> List[Dict[str, Any]]:
        """
        Compress messages to fit target token count
        
        Args:
            messages: List of messages
            target_tokens: Target token count
            strategy: Compression strategy
            
        Returns:
            Compressed messages
        """
        current_tokens = sum(TokenCounter.count_message_tokens(m) for m in messages)
        
        if current_tokens <= target_tokens:
            return messages  # No compression needed
        
        logger.info(f"Compressing {current_tokens} tokens to {target_tokens}")
        
        if strategy == CompressionStrategy.SUMMARIZATION:
            return self._compress_by_summarization(messages, target_tokens)
        elif strategy == CompressionStrategy.EXTRACTION:
            return self._compress_by_extraction(messages)
        elif strategy == CompressionStrategy.CHUNKING:
            return self._compress_by_chunking(messages, target_tokens)
        else:
            return messages[:target_tokens // 100]  # Fallback: truncate
    
    def _compress_by_summarization(
        self,
        messages: List[Dict[str, Any]],
        target_tokens: int
    ) -> List[Dict[str, Any]]:
        """Compress by summarizing older messages"""
        if len(messages) <= 2:
            return messages
        
        # Keep most recent messages, summarize older ones
        recent_count = len(messages) // 3
        recent_messages = messages[-recent_count:]
        old_messages = messages[:-recent_count]
        
        # Summarize old messages
        old_content = "\n\n".join([
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in old_messages
        ])
        
        summary_prompt = f"""Summarize the following conversation concisely, preserving key information:

{old_content}

Summary:"""
        
        summary = self.llm_function(summary_prompt)
        
        # Create compressed context
        compressed = [
            {"role": "system", "content": f"Previous conversation summary: {summary}"}
        ] + recent_messages
        
        return compressed
    
    def _compress_by_extraction(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract key information only"""
        # Keep messages with questions and important keywords
        important_keywords = ["error", "help", "problem", "how", "what", "why", "when", "where"]
        
        filtered = []
        for msg in messages:
            content = msg.get("content", "").lower()
            if any(kw in content for kw in important_keywords):
                filtered.append(msg)
        
        # Always keep at least the last 2 messages
        if len(filtered) < 2:
            filtered = messages[-2:]
        
        return filtered
    
    def _compress_by_chunking(
        self,
        messages: List[Dict[str, Any]],
        target_tokens: int
    ) -> List[Dict[str, Any]]:
        """Chunk messages to fit target"""
        result = []
        current_tokens = 0
        
        # Start from most recent
        for msg in reversed(messages):
            msg_tokens = TokenCounter.count_message_tokens(msg)
            if current_tokens + msg_tokens <= target_tokens:
                result.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        return result


class HierarchicalMemory:
    """Hierarchical memory organization"""
    
    def __init__(self):
        self.nodes: Dict[str, MemoryNode] = {}
        self.node_counter = 0
        self.roots: List[str] = []  # Root node IDs
        
    def create_node(
        self,
        content: str,
        level: MemoryLevel,
        parent_id: Optional[str] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryNode:
        """
        Create memory node
        
        Args:
            content: Memory content
            level: Memory level
            parent_id: Parent node ID
            importance: Importance score
            metadata: Additional metadata
            
        Returns:
            Created MemoryNode
        """
        self.node_counter += 1
        node_id = f"node_{level.value}_{self.node_counter}_{int(time.time())}"
        
        node = MemoryNode(
            id=node_id,
            level=level,
            content=content,
            summary=None,
            children=[],
            parent=parent_id,
            metadata=metadata or {},
            importance=importance,
            access_count=0,
            created_at=time.time(),
            last_accessed=time.time()
        )
        
        self.nodes[node_id] = node
        
        # Update parent
        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id].children.append(node_id)
        else:
            self.roots.append(node_id)
        
        return node
    
    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        """Get node and update access"""
        node = self.nodes.get(node_id)
        if node:
            node.access_count += 1
            node.last_accessed = time.time()
        return node
    
    def get_path_to_root(self, node_id: str) -> List[MemoryNode]:
        """Get path from node to root"""
        path = []
        current_id = node_id
        
        while current_id:
            node = self.nodes.get(current_id)
            if not node:
                break
            path.append(node)
            current_id = node.parent
        
        return path
    
    def get_children_recursive(self, node_id: str) -> List[MemoryNode]:
        """Get all children recursively"""
        children = []
        node = self.nodes.get(node_id)
        
        if not node:
            return children
        
        for child_id in node.children:
            child = self.nodes.get(child_id)
            if child:
                children.append(child)
                children.extend(self.get_children_recursive(child_id))
        
        return children
    
    def promote_to_longterm(self, node_id: str, summary: str):
        """Promote node to long-term memory with summary"""
        node = self.nodes.get(node_id)
        if not node:
            return
        
        # Create long-term node
        lt_node = self.create_node(
            content=summary,
            level=MemoryLevel.LONG_TERM,
            importance=node.importance,
            metadata={
                "original_node": node_id,
                "promoted_at": time.time(),
                **node.metadata
            }
        )
        
        logger.info(f"Promoted node {node_id} to long-term memory")
        return lt_node


class MemoryRetriever:
    """Retrieve relevant memories"""
    
    def __init__(self, hierarchical_memory: HierarchicalMemory):
        self.memory = hierarchical_memory
    
    def retrieve_by_level(
        self,
        level: MemoryLevel,
        limit: int = 10
    ) -> List[MemoryNode]:
        """Retrieve memories by level"""
        nodes = [n for n in self.memory.nodes.values() if n.level == level]
        
        # Sort by importance and recency
        nodes.sort(
            key=lambda n: n.importance * (1.0 / (time.time() - n.last_accessed + 1)),
            reverse=True
        )
        
        return nodes[:limit]
    
    def retrieve_by_importance(
        self,
        min_importance: float = 0.7,
        limit: int = 10
    ) -> List[MemoryNode]:
        """Retrieve important memories"""
        nodes = [n for n in self.memory.nodes.values() if n.importance >= min_importance]
        nodes.sort(key=lambda n: n.importance, reverse=True)
        return nodes[:limit]
    
    def retrieve_recent(
        self,
        hours: int = 24,
        limit: int = 10
    ) -> List[MemoryNode]:
        """Retrieve recent memories"""
        cutoff = time.time() - (hours * 3600)
        nodes = [n for n in self.memory.nodes.values() if n.created_at >= cutoff]
        nodes.sort(key=lambda n: n.created_at, reverse=True)
        return nodes[:limit]
    
    def retrieve_context(
        self,
        max_tokens: int = 4000
    ) -> str:
        """
        Retrieve context for current query
        
        Args:
            max_tokens: Maximum tokens to retrieve
            
        Returns:
            Context string
        """
        # Get working memory (most recent)
        working = self.retrieve_by_level(MemoryLevel.WORKING, limit=5)
        
        # Get important long-term memories
        longterm = self.retrieve_by_importance(min_importance=0.8, limit=3)
        
        # Combine
        all_memories = working + longterm
        
        # Build context
        context_parts = []
        current_tokens = 0
        
        for node in all_memories:
            content = node.summary if node.summary else node.content
            tokens = TokenCounter.count_tokens(content)
            
            if current_tokens + tokens <= max_tokens:
                context_parts.append(content)
                current_tokens += tokens
            else:
                break
        
        return "\n\n".join(context_parts)


class LongtermMemorySystem:
    """
    Unified Long-term Memory System
    Manages extended context beyond session limits
    """
    
    def __init__(self, llm_function, max_context_tokens: int = 8000):
        self.llm_function = llm_function
        self.max_context_tokens = max_context_tokens
        
        self.context_window = ContextWindow(
            max_tokens=max_context_tokens,
            current_tokens=0,
            messages=[]
        )
        
        self.compressor = ContextCompressor(llm_function)
        self.hierarchical_memory = HierarchicalMemory()
        self.retriever = MemoryRetriever(self.hierarchical_memory)
        
        self.enabled = True
        logger.info("✅ Long-term Memory System initialized")
    
    def add_to_working_memory(
        self,
        content: str,
        role: str = "user",
        importance: float = 0.5
    ):
        """
        Add to working memory
        
        Args:
            content: Content to add
            role: Message role
            importance: Importance score
        """
        # Create memory node
        node = self.hierarchical_memory.create_node(
            content=content,
            level=MemoryLevel.WORKING,
            importance=importance,
            metadata={"role": role}
        )
        
        # Add to context window
        message = {"role": role, "content": content}
        token_count = TokenCounter.count_message_tokens(message)
        
        if not self.context_window.can_fit(token_count):
            # Compress if needed
            self._compress_context()
        
        self.context_window.add_message(message, token_count)
    
    def store_longterm(
        self,
        content: str,
        summary: Optional[str] = None,
        importance: float = 0.8
    ) -> MemoryNode:
        """
        Store in long-term memory
        
        Args:
            content: Content to store
            summary: Optional summary
            importance: Importance score
            
        Returns:
            Created MemoryNode
        """
        node = self.hierarchical_memory.create_node(
            content=content,
            level=MemoryLevel.LONG_TERM,
            importance=importance
        )
        
        # Generate summary if not provided
        if not summary and len(content) > 500:
            summary = self._generate_summary(content)
        
        node.summary = summary
        logger.info(f"Stored in long-term memory: {node.id}")
        return node
    
    def retrieve_context(
        self,
        query: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Retrieve relevant context
        
        Args:
            query: Optional query for relevance
            max_tokens: Maximum tokens (defaults to half window)
            
        Returns:
            Context string
        """
        if max_tokens is None:
            max_tokens = self.max_context_tokens // 2
        
        context = self.retriever.retrieve_context(max_tokens)
        return context
    
    def compress_context(
        self,
        strategy: str = "summarization",
        target_ratio: float = 0.5
    ):
        """
        Manually compress context
        
        Args:
            strategy: Compression strategy
            target_ratio: Target compression ratio
        """
        self._compress_context(
            strategy=CompressionStrategy(strategy),
            target_ratio=target_ratio
        )
    
    def promote_to_core(self, content: str, importance: float = 1.0):
        """
        Promote to core memory (essential facts)
        
        Args:
            content: Content to promote
            importance: Importance (default max)
        """
        node = self.hierarchical_memory.create_node(
            content=content,
            level=MemoryLevel.CORE,
            importance=importance
        )
        logger.info(f"Promoted to core memory: {node.id}")
        return node
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        nodes_by_level = {}
        for level in MemoryLevel:
            nodes_by_level[level.value] = len(
                [n for n in self.hierarchical_memory.nodes.values() if n.level == level]
            )
        
        return {
            "total_nodes": len(self.hierarchical_memory.nodes),
            "by_level": nodes_by_level,
            "context_usage": self.context_window.get_usage_ratio(),
            "context_messages": len(self.context_window.messages),
            "context_tokens": self.context_window.current_tokens,
            "max_tokens": self.max_context_tokens
        }
    
    def _compress_context(
        self,
        strategy: CompressionStrategy = CompressionStrategy.SUMMARIZATION,
        target_ratio: float = 0.7
    ):
        """Compress context window"""
        target_tokens = int(self.max_context_tokens * target_ratio)
        
        compressed_messages = self.compressor.compress_messages(
            self.context_window.messages,
            target_tokens,
            strategy
        )
        
        # Update window
        self.context_window.messages = compressed_messages
        self.context_window.current_tokens = sum(
            TokenCounter.count_message_tokens(m) for m in compressed_messages
        )
        self.context_window.compressed = True
        
        logger.info(f"Context compressed to {self.context_window.current_tokens} tokens")
    
    def _generate_summary(self, content: str) -> str:
        """Generate summary of content"""
        prompt = f"""Summarize the following content in 1-2 sentences:

{content}

Summary:"""
        
        summary = self.llm_function(prompt)
        return summary.strip()


# Convenience function
def create_longterm_memory_system(
    llm_function,
    max_context_tokens: int = 8000
) -> LongtermMemorySystem:
    """
    Create long-term memory system
    
    Args:
        llm_function: LLM function for summarization
        max_context_tokens: Maximum context window tokens
        
    Returns:
        LongtermMemorySystem instance
    """
    return LongtermMemorySystem(llm_function, max_context_tokens)
