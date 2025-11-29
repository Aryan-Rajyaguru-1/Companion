#!/usr/bin/env python3
"""
Streaming Response System
=========================

Enables real-time streaming of AI responses:
- Token-by-token streaming
- Server-Sent Events (SSE) support
- WebSocket support
- Chunk processing
- Stream interruption
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable
from dataclasses import dataclass
from enum import Enum
import json
import time

logger = logging.getLogger(__name__)


class StreamEvent(Enum):
    """Types of streaming events"""
    START = "start"
    TOKEN = "token"
    CHUNK = "chunk"
    TOOL_CALL = "tool_call"
    THINKING = "thinking"
    DONE = "done"
    ERROR = "error"


@dataclass
class StreamChunk:
    """Single chunk in stream"""
    event: StreamEvent
    content: str
    metadata: Dict[str, Any]
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "event": self.event.value,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }
    
    def to_sse(self) -> str:
        """Convert to Server-Sent Events format"""
        data = json.dumps(self.to_dict())
        return f"data: {data}\n\n"
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


class StreamBuffer:
    """Buffer for managing streaming data"""
    
    def __init__(self, max_size: int = 1000):
        self.buffer: List[StreamChunk] = []
        self.max_size = max_size
        self.current_content = ""
        
    def add(self, chunk: StreamChunk):
        """Add chunk to buffer"""
        self.buffer.append(chunk)
        
        # Keep buffer size manageable
        if len(self.buffer) > self.max_size:
            self.buffer.pop(0)
        
        # Update current content
        if chunk.event == StreamEvent.TOKEN or chunk.event == StreamEvent.CHUNK:
            self.current_content += chunk.content
    
    def get_full_content(self) -> str:
        """Get complete accumulated content"""
        return self.current_content
    
    def clear(self):
        """Clear buffer"""
        self.buffer.clear()
        self.current_content = ""


class StreamController:
    """Control streaming behavior"""
    
    def __init__(self):
        self.is_stopped = False
        self.is_paused = False
        self.callbacks: Dict[StreamEvent, List[Callable]] = {}
        
    def stop(self):
        """Stop streaming"""
        self.is_stopped = True
        
    def pause(self):
        """Pause streaming"""
        self.is_paused = True
        
    def resume(self):
        """Resume streaming"""
        self.is_paused = False
        
    def should_continue(self) -> bool:
        """Check if should continue streaming"""
        return not self.is_stopped
    
    def register_callback(self, event: StreamEvent, callback: Callable):
        """Register callback for event"""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)
    
    def trigger_callbacks(self, event: StreamEvent, chunk: StreamChunk):
        """Trigger callbacks for event"""
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback(chunk)
                except Exception as e:
                    logger.error(f"Callback error: {e}")


class TokenStreamProcessor:
    """Process token-level streaming"""
    
    def __init__(self, delay_ms: int = 0):
        self.delay_ms = delay_ms  # Simulated delay between tokens
        
    async def stream_tokens(
        self,
        text: str,
        controller: StreamController
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream text token by token
        
        Args:
            text: Text to stream
            controller: Stream controller
            
        Yields:
            StreamChunk for each token
        """
        # Start event
        yield StreamChunk(
            event=StreamEvent.START,
            content="",
            metadata={"total_chars": len(text)},
            timestamp=time.time()
        )
        
        # Stream tokens (simplified - real implementation would use tokenizer)
        words = text.split()
        for i, word in enumerate(words):
            if not controller.should_continue():
                break
            
            # Wait if paused
            while controller.is_paused:
                await asyncio.sleep(0.1)
            
            # Add space except for first word
            token = word if i == 0 else f" {word}"
            
            yield StreamChunk(
                event=StreamEvent.TOKEN,
                content=token,
                metadata={"position": i, "total": len(words)},
                timestamp=time.time()
            )
            
            # Simulate processing delay
            if self.delay_ms > 0:
                await asyncio.sleep(self.delay_ms / 1000)
        
        # Done event
        yield StreamChunk(
            event=StreamEvent.DONE,
            content="",
            metadata={"total_tokens": len(words)},
            timestamp=time.time()
        )


class ChunkStreamProcessor:
    """Process chunk-level streaming (sentences/paragraphs)"""
    
    def __init__(self, chunk_size: str = "sentence"):
        """
        Args:
            chunk_size: 'sentence', 'paragraph', or 'word'
        """
        self.chunk_size = chunk_size
        
    def split_into_chunks(self, text: str) -> List[str]:
        """Split text into chunks based on strategy"""
        if self.chunk_size == "sentence":
            # Split by sentence
            import re
            chunks = re.split(r'([.!?]+)', text)
            # Recombine sentences with their punctuation
            result = []
            for i in range(0, len(chunks)-1, 2):
                result.append(chunks[i] + (chunks[i+1] if i+1 < len(chunks) else ""))
            return result
        
        elif self.chunk_size == "paragraph":
            return text.split('\n\n')
        
        else:  # word
            return text.split()
    
    async def stream_chunks(
        self,
        text: str,
        controller: StreamController
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream text in chunks
        
        Args:
            text: Text to stream
            controller: Stream controller
            
        Yields:
            StreamChunk for each chunk
        """
        # Start event
        yield StreamChunk(
            event=StreamEvent.START,
            content="",
            metadata={"chunk_size": self.chunk_size},
            timestamp=time.time()
        )
        
        # Split and stream
        chunks = self.split_into_chunks(text)
        for i, chunk in enumerate(chunks):
            if not controller.should_continue():
                break
            
            while controller.is_paused:
                await asyncio.sleep(0.1)
            
            yield StreamChunk(
                event=StreamEvent.CHUNK,
                content=chunk,
                metadata={
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "chunk_type": self.chunk_size
                },
                timestamp=time.time()
            )
        
        # Done
        yield StreamChunk(
            event=StreamEvent.DONE,
            content="",
            metadata={"total_chunks": len(chunks)},
            timestamp=time.time()
        )


class LLMStreamAdapter:
    """Adapt various LLM streaming formats"""
    
    @staticmethod
    async def stream_openai(
        openai_stream,
        controller: StreamController
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Adapt OpenAI streaming response
        
        Args:
            openai_stream: OpenAI streaming response
            controller: Stream controller
            
        Yields:
            StreamChunk
        """
        yield StreamChunk(
            event=StreamEvent.START,
            content="",
            metadata={"provider": "openai"},
            timestamp=time.time()
        )
        
        try:
            async for chunk in openai_stream:
                if not controller.should_continue():
                    break
                
                # Extract content from OpenAI format
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        yield StreamChunk(
                            event=StreamEvent.TOKEN,
                            content=delta.content,
                            metadata={"provider": "openai"},
                            timestamp=time.time()
                        )
        
        except Exception as e:
            yield StreamChunk(
                event=StreamEvent.ERROR,
                content=str(e),
                metadata={"provider": "openai", "error": str(e)},
                timestamp=time.time()
            )
        
        yield StreamChunk(
            event=StreamEvent.DONE,
            content="",
            metadata={"provider": "openai"},
            timestamp=time.time()
        )
    
    @staticmethod
    async def stream_anthropic(
        anthropic_stream,
        controller: StreamController
    ) -> AsyncGenerator[StreamChunk, None]:
        """Adapt Anthropic/Claude streaming"""
        yield StreamChunk(
            event=StreamEvent.START,
            content="",
            metadata={"provider": "anthropic"},
            timestamp=time.time()
        )
        
        try:
            async for chunk in anthropic_stream:
                if not controller.should_continue():
                    break
                
                # Extract from Anthropic format
                if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                    yield StreamChunk(
                        event=StreamEvent.TOKEN,
                        content=chunk.delta.text,
                        metadata={"provider": "anthropic"},
                        timestamp=time.time()
                    )
        
        except Exception as e:
            yield StreamChunk(
                event=StreamEvent.ERROR,
                content=str(e),
                metadata={"error": str(e)},
                timestamp=time.time()
            )
        
        yield StreamChunk(
            event=StreamEvent.DONE,
            content="",
            metadata={"provider": "anthropic"},
            timestamp=time.time()
        )


class StreamingSystem:
    """
    Unified Streaming Response System
    Handles all streaming needs
    """
    
    def __init__(self):
        self.token_processor = TokenStreamProcessor()
        self.chunk_processor = ChunkStreamProcessor()
        self.adapter = LLMStreamAdapter()
        
        self.enabled = True
        logger.info("✅ Streaming System initialized")
    
    async def stream_response(
        self,
        content: str,
        stream_type: str = "token",
        controller: Optional[StreamController] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream a response
        
        Args:
            content: Content to stream
            stream_type: 'token', 'chunk', or 'sentence'
            controller: Optional controller
            
        Yields:
            StreamChunk
        """
        if controller is None:
            controller = StreamController()
        
        if stream_type == "token":
            async for chunk in self.token_processor.stream_tokens(content, controller):
                yield chunk
        
        elif stream_type in ["chunk", "sentence", "paragraph"]:
            self.chunk_processor.chunk_size = stream_type
            async for chunk in self.chunk_processor.stream_chunks(content, controller):
                yield chunk
        
        else:
            # Default: return all at once
            yield StreamChunk(
                event=StreamEvent.START,
                content="",
                metadata={},
                timestamp=time.time()
            )
            yield StreamChunk(
                event=StreamEvent.CHUNK,
                content=content,
                metadata={},
                timestamp=time.time()
            )
            yield StreamChunk(
                event=StreamEvent.DONE,
                content="",
                metadata={},
                timestamp=time.time()
            )
    
    async def stream_with_thinking(
        self,
        llm_stream_function,
        query: str,
        show_reasoning: bool = True,
        controller: Optional[StreamController] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream response with thinking/reasoning steps
        
        Args:
            llm_stream_function: Async function that yields LLM stream
            query: User query
            show_reasoning: Show thinking process
            controller: Optional controller
            
        Yields:
            StreamChunk with thinking and response
        """
        if controller is None:
            controller = StreamController()
        
        # Start
        yield StreamChunk(
            event=StreamEvent.START,
            content="",
            metadata={"show_reasoning": show_reasoning},
            timestamp=time.time()
        )
        
        # Thinking phase (if enabled)
        if show_reasoning:
            yield StreamChunk(
                event=StreamEvent.THINKING,
                content="🧠 Analyzing query...",
                metadata={"phase": "analysis"},
                timestamp=time.time()
            )
            
            await asyncio.sleep(0.5)  # Simulate thinking
            
            yield StreamChunk(
                event=StreamEvent.THINKING,
                content="🔍 Gathering information...",
                metadata={"phase": "gathering"},
                timestamp=time.time()
            )
        
        # Stream actual response
        try:
            async for chunk in llm_stream_function(query):
                if not controller.should_continue():
                    break
                yield chunk
        
        except Exception as e:
            yield StreamChunk(
                event=StreamEvent.ERROR,
                content=str(e),
                metadata={"error": str(e)},
                timestamp=time.time()
            )
        
        # Done
        yield StreamChunk(
            event=StreamEvent.DONE,
            content="",
            metadata={},
            timestamp=time.time()
        )
    
    async def collect_stream(
        self,
        stream: AsyncGenerator[StreamChunk, None]
    ) -> str:
        """
        Collect all content from stream
        
        Args:
            stream: Stream to collect
            
        Returns:
            Complete content
        """
        content = ""
        async for chunk in stream:
            if chunk.event in [StreamEvent.TOKEN, StreamEvent.CHUNK]:
                content += chunk.content
        return content
    
    def create_controller(self) -> StreamController:
        """Create a new stream controller"""
        return StreamController()


# Convenience function
def create_streaming_system() -> StreamingSystem:
    """Create and return streaming system"""
    return StreamingSystem()


# Helper for synchronous use
def stream_to_list(async_generator) -> List[StreamChunk]:
    """Convert async generator to list (for testing)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        chunks = []
        async def collect():
            async for chunk in async_generator:
                chunks.append(chunk)
        loop.run_until_complete(collect())
        return chunks
    finally:
        loop.close()
