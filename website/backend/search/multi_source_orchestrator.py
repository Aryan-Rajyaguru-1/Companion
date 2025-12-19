#!/usr/bin/env python3
"""
Multi-Source Search Orchestrator
================================

Coordinates searches across multiple specialized sources simultaneously
Similar to Perplexity's search architecture
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class SourceType(Enum):
    """Types of search sources"""
    WEB = "web"                    # General web search
    ACADEMIC = "academic"          # Google Scholar, arXiv
    NEWS = "news"                  # Recent news articles
    REDDIT = "reddit"              # Reddit discussions
    YOUTUBE = "youtube"            # Video content
    WIKIPEDIA = "wikipedia"        # Encyclopedia
    STACKOVERFLOW = "stackoverflow"  # Code Q&A
    GITHUB = "github"              # Code repositories
    TWITTER = "twitter"            # Social media
    SHOPPING = "shopping"          # Product search

class FocusMode(Enum):
    """Search focus modes (like Perplexity)"""
    ALL = "all"                    # Search everything
    ACADEMIC = "academic"          # Scholarly sources only
    NEWS = "news"                  # Recent news only
    VIDEO = "video"                # YouTube only
    REDDIT = "reddit"              # Reddit only
    CODE = "code"                  # GitHub + StackOverflow
    SHOPPING = "shopping"          # Shopping sites
    SOCIAL = "social"              # Twitter + Reddit

@dataclass
class SearchSource:
    """Individual search result from a source"""
    title: str
    url: str
    snippet: str
    source_type: SourceType
    source_name: str
    published_date: Optional[datetime]
    credibility_score: float
    relevance_score: float
    content: str = ""
    metadata: Dict[str, Any] = None

@dataclass
class AggregatedResult:
    """Aggregated search results from multiple sources"""
    query: str
    focus_mode: FocusMode
    sources: List[SearchSource]
    total_sources_searched: int
    search_time_ms: float
    suggested_follow_ups: List[str]
    summary: str = ""
    citations: Dict[int, SearchSource] = None

class MultiSourceOrchestrator:
    """
    Orchestrates searches across multiple specialized sources

    Features:
    - Parallel searching (10+ sources simultaneously)
    - Smart source selection based on query intent
    - Credibility scoring
    - Result deduplication
    - Citation management
    """

    def __init__(self):
        self.searchers = self._initialize_searchers()
        self.citation_counter = 0
        logger.info("🔍 Multi-Source Orchestrator initialized")

    def _initialize_searchers(self) -> Dict[SourceType, Any]:
        """Initialize all search backends"""
        return {
            SourceType.WEB: WebSearcher(),
            SourceType.ACADEMIC: AcademicSearcher(),
            SourceType.NEWS: NewsSearcher(),
            SourceType.REDDIT: RedditSearcher(),
            SourceType.YOUTUBE: YouTubeSearcher(),
            SourceType.WIKIPEDIA: WikipediaSearcher(),
            SourceType.STACKOVERFLOW: StackOverflowSearcher(),
            SourceType.GITHUB: GitHubSearcher(),
        }

    async def search(
        self,
        query: str,
        focus_mode: FocusMode = FocusMode.ALL,
        max_sources: int = 10,
        require_recent: bool = False
    ) -> AggregatedResult:
        """
        Search across multiple sources based on focus mode

        Args:
            query: Search query
            focus_mode: Which sources to prioritize
            max_sources: Maximum number of sources to return
            require_recent: Only return recent results (news, etc.)

        Returns:
            Aggregated results with citations
        """
        start_time = datetime.now()

        # Determine which sources to search based on focus mode
        sources_to_search = self._select_sources(focus_mode, query)

        logger.info(f"🔍 Searching {len(sources_to_search)} sources for: {query}")

        # Search all sources in parallel
        search_tasks = [
            self._search_source(source_type, query, require_recent)
            for source_type in sources_to_search
        ]

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Filter out errors and flatten results
        all_sources = []
        for result in results:
            if isinstance(result, list):
                all_sources.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"Search failed: {result}")

        # Score and rank results
        ranked_sources = self._rank_sources(all_sources, query)

        # Take top N sources
        top_sources = ranked_sources[:max_sources]

        # Assign citation numbers
        citations = self._assign_citations(top_sources)

        # Generate summary with citations
        summary = await self._generate_summary(query, top_sources, citations)

        # Generate follow-up questions
        follow_ups = await self._generate_follow_ups(query, top_sources)

        search_time = (datetime.now() - start_time).total_seconds() * 1000

        return AggregatedResult(
            query=query,
            focus_mode=focus_mode,
            sources=top_sources,
            total_sources_searched=len(all_sources),
            search_time_ms=search_time,
            suggested_follow_ups=follow_ups,
            summary=summary,
            citations=citations
        )

    def _select_sources(self, focus_mode: FocusMode, query: str) -> List[SourceType]:
        """Select which sources to search based on focus mode"""
        focus_map = {
            FocusMode.ALL: [
                SourceType.WEB,
                SourceType.WIKIPEDIA,
                SourceType.REDDIT,
                SourceType.YOUTUBE,
                SourceType.STACKOVERFLOW
            ],
            FocusMode.ACADEMIC: [
                SourceType.ACADEMIC,
                SourceType.WIKIPEDIA
            ],
            FocusMode.NEWS: [
                SourceType.NEWS,
                SourceType.TWITTER
            ],
            FocusMode.VIDEO: [
                SourceType.YOUTUBE
            ],
            FocusMode.REDDIT: [
                SourceType.REDDIT
            ],
            FocusMode.CODE: [
                SourceType.STACKOVERFLOW,
                SourceType.GITHUB
            ],
            FocusMode.SHOPPING: [
                SourceType.SHOPPING
            ],
            FocusMode.SOCIAL: [
                SourceType.TWITTER,
                SourceType.REDDIT
            ]
        }

        # Also do intent detection
        if self._is_code_question(query):
            return focus_map[FocusMode.CODE]

        return focus_map.get(focus_mode, focus_map[FocusMode.ALL])

    def _is_code_question(self, query: str) -> bool:
        """Detect if query is about coding"""
        code_keywords = [
            'code', 'programming', 'python', 'javascript',
            'function', 'error', 'bug', 'algorithm',
            'how to implement', 'syntax'
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in code_keywords)

    async def _search_source(
        self,
        source_type: SourceType,
        query: str,
        require_recent: bool
    ) -> List[SearchSource]:
        """Search a single source"""
        searcher = self.searchers.get(source_type)
        if not searcher:
            return []

        try:
            results = await searcher.search(query, require_recent)
            return results
        except Exception as e:
            logger.error(f"Error searching {source_type}: {e}")
            return []

    def _rank_sources(
        self,
        sources: List[SearchSource],
        query: str
    ) -> List[SearchSource]:
        """
        Rank sources by relevance and credibility

        Ranking factors:
        1. Relevance score (from search engine)
        2. Credibility score (domain authority)
        3. Recency (for time-sensitive queries)
        4. Diversity (prefer different sources)
        """
        # Calculate composite score
        for source in sources:
            relevance_weight = 0.5
            credibility_weight = 0.3
            recency_weight = 0.2

            # Recency score
            if source.published_date:
                days_old = (datetime.now() - source.published_date).days
                recency_score = max(0, 1.0 - (days_old / 365))
            else:
                recency_score = 0.5

            # Composite score
            source.relevance_score = (
                source.relevance_score * relevance_weight +
                source.credibility_score * credibility_weight +
                recency_score * recency_weight
            )

        # Sort by composite score
        sources.sort(key=lambda x: x.relevance_score, reverse=True)

        # Ensure diversity (no more than 2 per domain)
        diverse_sources = []
        domain_counts = {}

        for source in sources:
            domain = self._extract_domain(source.url)
            count = domain_counts.get(domain, 0)

            if count < 2:  # Max 2 per domain
                diverse_sources.append(source)
                domain_counts[domain] = count + 1

        return diverse_sources

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        return urlparse(url).netloc

    def _assign_citations(
        self,
        sources: List[SearchSource]
    ) -> Dict[int, SearchSource]:
        """Assign citation numbers to sources"""
        citations = {}
        for i, source in enumerate(sources, 1):
            citations[i] = source
        return citations

    async def _generate_summary(
        self,
        query: str,
        sources: List[SearchSource],
        citations: Dict[int, SearchSource]
    ) -> str:
        """
        Generate summary with inline citations

        Example output:
        "Python is a high-level programming language [1].
        It was created by Guido van Rossum in 1991 [2].
        Python is known for its simple syntax [3] and extensive libraries [4]."
        """
        # Prepare context from sources
        context = "\n\n".join([
            f"[{i}] {source.source_name}: {source.snippet}"
            for i, source in citations.items()
        ])

        prompt = f"""Based on these sources, answer the query with inline citations:

Query: {query}

Sources:
{context}

Instructions:
1. Provide a comprehensive answer
2. Use inline citations [1], [2], etc. after each claim
3. Only cite information that appears in the sources
4. Be concise but complete
5. Use natural language

Answer:"""

        # Use brain to generate summary
        # This would call your brain.py
        summary = await self._call_ai_for_summary(prompt)

        return summary

    async def _call_ai_for_summary(self, prompt: str) -> str:
        """Call AI model to generate summary"""
        # This would integrate with your brain.py
        # For now, placeholder
        return "Summary with citations [1] [2]"

    async def _generate_follow_ups(
        self,
        query: str,
        sources: List[SearchSource]
    ) -> List[str]:
        """Generate suggested follow-up questions"""
        prompt = f"""Based on this query and search results, suggest 3 related follow-up questions:

Original Query: {query}

Sources: {[s.title for s in sources[:5]]}

Generate questions that:
1. Dive deeper into the topic
2. Explore related aspects
3. Are natural and conversational

Follow-up questions (one per line):"""

        # Call AI to generate
        response = await self._call_ai_for_summary(prompt)

        # Parse response into list
        follow_ups = [q.strip() for q in response.split('\n') if q.strip()]
        return follow_ups[:3]


# Individual Searchers

class WebSearcher:
    """General web search using DuckDuckGo, Bing, etc."""
    async def search(self, query: str, require_recent: bool) -> List[SearchSource]:
        # Implement web search
        pass

class AcademicSearcher:
    """Search academic papers (Google Scholar, arXiv, PubMed)"""
    async def search(self, query: str, require_recent: bool) -> List[SearchSource]:
        # Implement academic search
        pass

class NewsSearcher:
    """Search recent news articles"""
    async def search(self, query: str, require_recent: bool) -> List[SearchSource]:
        # Implement news search
        pass

class RedditSearcher:
    """Search Reddit discussions"""
    async def search(self, query: str, require_recent: bool) -> List[SearchSource]:
        # Implement Reddit search using Reddit API
        pass

class YouTubeSearcher:
    """Search YouTube videos"""
    async def search(self, query: str, require_recent: bool) -> List[SearchSource]:
        # Implement YouTube search
        pass

class WikipediaSearcher:
    """Search Wikipedia"""
    async def search(self, query: str, require_recent: bool) -> List[SearchSource]:
        # Implement Wikipedia search
        pass

class StackOverflowSearcher:
    """Search StackOverflow questions"""
    async def search(self, query: str, require_recent: bool) -> List[SearchSource]:
        # Implement StackOverflow search
        pass

class GitHubSearcher:
    """Search GitHub repositories and code"""
    async def search(self, query: str, require_recent: bool) -> List[SearchSource]:
        # Implement GitHub search
        pass