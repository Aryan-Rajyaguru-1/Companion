#!/usr/bin/env python3
"""
Focus Mode System
================

Different search modes like Perplexity:
- All: Search everything
- Academic: Scholarly sources
- Writing: Creative assistance
- Video: YouTube content
- Reddit: Community discussions
- Code: Programming help
"""

from enum import Enum
from typing import Dict, List, Any
from dataclasses import dataclass

class FocusMode(Enum):
    ALL = "all"
    ACADEMIC = "academic"
    WRITING = "writing"
    VIDEO = "video"
    REDDIT = "reddit"
    CODE = "code"
    NEWS = "news"
    SHOPPING = "shopping"

@dataclass
class FocusModeConfig:
    """Configuration for each focus mode"""
    name: str
    description: str
    icon: str
    sources: List[str]
    ai_instructions: str
    max_sources: int

FOCUS_CONFIGS = {
    FocusMode.ALL: FocusModeConfig(
        name="All",
        description="Search across all sources",
        icon="🌐",
        sources=["web", "wikipedia", "reddit", "youtube"],
        ai_instructions="Provide a comprehensive answer using diverse sources.",
        max_sources=10
    ),

    FocusMode.ACADEMIC: FocusModeConfig(
        name="Academic",
        description="Scholarly sources and papers",
        icon="🎓",
        sources=["google_scholar", "arxiv", "pubmed", "wikipedia"],
        ai_instructions="Provide academic, well-researched answers with proper citations. Use formal language.",
        max_sources=8
    ),

    FocusMode.WRITING: FocusModeConfig(
        name="Writing",
        description="Creative and writing assistance",
        icon="✍️",
        sources=["web", "wikipedia"],
        ai_instructions="Help with creative writing, editing, and composition. Be creative and stylistic.",
        max_sources=5
    ),

    FocusMode.VIDEO: FocusModeConfig(
        name="Video",
        description="YouTube and video content",
        icon="🎥",
        sources=["youtube"],
        ai_instructions="Summarize and reference video content. Include timestamps if available.",
        max_sources=5
    ),

    FocusMode.REDDIT: FocusModeConfig(
        name="Reddit",
        description="Community discussions",
        icon="💬",
        sources=["reddit"],
        ai_instructions="Provide insights from community discussions. Include popular opinions and debates.",
        max_sources=8
    ),

    FocusMode.CODE: FocusModeConfig(
        name="Code",
        description="Programming help and code examples",
        icon="💻",
        sources=["stackoverflow", "github", "web"],
        ai_instructions="Provide code examples, best practices, and technical solutions.",
        max_sources=6
    ),

    FocusMode.NEWS: FocusModeConfig(
        name="News",
        description="Recent news and updates",
        icon="📰",
        sources=["news", "twitter"],
        ai_instructions="Provide up-to-date information from recent news. Note publication dates.",
        max_sources=8
    )
}

class FocusModeManager:
    """Manages focus modes for searches"""

    def get_config(self, mode: FocusMode) -> FocusModeConfig:
        """Get configuration for a focus mode"""
        return FOCUS_CONFIGS[mode]

    def detect_best_mode(self, query: str) -> FocusMode:
        """
        Automatically detect best focus mode from query

        Examples:
        - "What does research say about..." → ACADEMIC
        - "Help me debug this Python code" → CODE
        - "What's trending on Reddit about..." → REDDIT
        - "Show me videos about..." → VIDEO
        """
        query_lower = query.lower()

        # Academic indicators
        if any(word in query_lower for word in [
            'research', 'study', 'paper', 'scientific',
            'peer-reviewed', 'journal', 'academic'
        ]):
            return FocusMode.ACADEMIC

        # Code indicators
        if any(word in query_lower for word in [
            'code', 'program', 'debug', 'error', 'function',
            'python', 'javascript', 'java', 'algorithm'
        ]):
            return FocusMode.CODE

        # Video indicators
        if any(word in query_lower for word in [
            'video', 'watch', 'youtube', 'tutorial'
        ]):
            return FocusMode.VIDEO

        # Reddit indicators
        if any(word in query_lower for word in [
            'reddit', 'discussion', 'community', 'what do people think'
        ]):
            return FocusMode.REDDIT

        # News indicators
        if any(word in query_lower for word in [
            'news', 'latest', 'recent', 'today', 'current events',
            'breaking', 'update'
        ]):
            return FocusMode.NEWS

        # Writing indicators
        if any(word in query_lower for word in [
            'write', 'essay', 'story', 'article', 'blog',
            'creative writing', 'grammar', 'style'
        ]):
            return FocusMode.WRITING

        # Default to ALL
        return FocusMode.ALL

    def get_available_modes(self) -> List[Dict[str, Any]]:
        """Get all available focus modes"""
        modes = []
        for mode in FocusMode:
            config = FOCUS_CONFIGS[mode]
            modes.append({
                'id': mode.value,
                'name': config.name,
                'description': config.description,
                'icon': config.icon,
                'sources': config.sources,
                'max_sources': config.max_sources
            })
        return modes

    def validate_mode(self, mode_str: str) -> bool:
        """Check if a mode string is valid"""
        try:
            FocusMode(mode_str)
            return True
        except ValueError:
            return False

    def get_mode_by_string(self, mode_str: str) -> FocusMode:
        """Get FocusMode enum from string"""
        return FocusMode(mode_str)

    def get_similar_modes(self, query: str) -> List[FocusMode]:
        """
        Get modes that might be relevant for a query

        Returns multiple modes if query could benefit from different perspectives
        """
        primary_mode = self.detect_best_mode(query)
        similar_modes = [primary_mode]

        # Add complementary modes
        if primary_mode == FocusMode.ACADEMIC:
            similar_modes.extend([FocusMode.NEWS, FocusMode.ALL])
        elif primary_mode == FocusMode.CODE:
            similar_modes.extend([FocusMode.REDDIT, FocusMode.ALL])
        elif primary_mode == FocusMode.REDDIT:
            similar_modes.extend([FocusMode.NEWS, FocusMode.ALL])
        elif primary_mode == FocusMode.VIDEO:
            similar_modes.extend([FocusMode.WRITING, FocusMode.ALL])

        # Remove duplicates and limit to 3
        unique_modes = list(dict.fromkeys(similar_modes))
        return unique_modes[:3]

    def get_mode_instructions(self, mode: FocusMode) -> str:
        """Get AI instructions for a specific mode"""
        return FOCUS_CONFIGS[mode].ai_instructions

    def customize_mode(self, mode: FocusMode, custom_config: Dict[str, Any]) -> FocusModeConfig:
        """
        Create a customized version of a focus mode

        Args:
            mode: Base mode to customize
            custom_config: Custom settings to override

        Returns:
            Customized FocusModeConfig
        """
        base_config = FOCUS_CONFIGS[mode]

        # Create customized config
        customized = FocusModeConfig(
            name=custom_config.get('name', base_config.name),
            description=custom_config.get('description', base_config.description),
            icon=custom_config.get('icon', base_config.icon),
            sources=custom_config.get('sources', base_config.sources),
            ai_instructions=custom_config.get('ai_instructions', base_config.ai_instructions),
            max_sources=custom_config.get('max_sources', base_config.max_sources)
        )

        return customized

    def create_custom_mode(
        self,
        name: str,
        description: str,
        sources: List[str],
        ai_instructions: str,
        icon: str = "🎯",
        max_sources: int = 10
    ) -> FocusModeConfig:
        """
        Create a completely custom focus mode

        Args:
            name: Display name
            description: Description
            sources: List of source types
            ai_instructions: Instructions for AI
            icon: Emoji icon
            max_sources: Maximum sources to return

        Returns:
            Custom FocusModeConfig
        """
        return FocusModeConfig(
            name=name,
            description=description,
            icon=icon,
            sources=sources,
            ai_instructions=ai_instructions,
            max_sources=max_sources
        )

    def get_mode_stats(self) -> Dict[str, Any]:
        """Get statistics about focus mode usage"""
        # This would track usage patterns
        # For now, return basic info
        return {
            'total_modes': len(FocusMode),
            'available_modes': [mode.value for mode in FocusMode],
            'most_popular': 'all',  # Would be tracked
            'usage_by_mode': {}  # Would be tracked
        }

    def recommend_mode(self, user_history: List[str] = None) -> FocusMode:
        """
        Recommend a focus mode based on user history

        Args:
            user_history: List of previous queries

        Returns:
            Recommended FocusMode
        """
        if not user_history:
            return FocusMode.ALL

        # Analyze history for patterns
        academic_count = 0
        code_count = 0
        reddit_count = 0

        for query in user_history[-10:]:  # Last 10 queries
            query_lower = query.lower()

            if any(word in query_lower for word in ['research', 'paper', 'study']):
                academic_count += 1
            elif any(word in query_lower for word in ['code', 'program', 'debug']):
                code_count += 1
            elif any(word in query_lower for word in ['reddit', 'discussion']):
                reddit_count += 1

        # Recommend based on most common pattern
        max_count = max(academic_count, code_count, reddit_count)

        if max_count == 0:
            return FocusMode.ALL
        elif academic_count == max_count:
            return FocusMode.ACADEMIC
        elif code_count == max_count:
            return FocusMode.CODE
        elif reddit_count == max_count:
            return FocusMode.REDDIT
        else:
            return FocusMode.ALL