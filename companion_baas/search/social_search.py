#!/usr/bin/env python3
"""
Social Media Search
==================

Search Reddit, Twitter, and other social platforms
"""

import praw
from typing import List, Dict
from datetime import datetime, timedelta
from companion_baas.search.multi_source_orchestrator import SearchSource, SourceType

class SocialSearchClient:
    """Search social media platforms"""

    def __init__(self):
        # Reddit API credentials (will be loaded from config)
        self.reddit_client_id = None
        self.reddit_client_secret = None
        self.reddit_user_agent = "DeepThink AI Assistant 1.0"
        self.reddit = None

        # Twitter credentials
        self.twitter_bearer_token = None

    def initialize_reddit(self, client_id: str, client_secret: str):
        """Initialize Reddit API client"""
        self.reddit_client_id = client_id
        self.reddit_client_secret = client_secret

        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=self.reddit_user_agent
        )

    async def search_reddit(
        self,
        query: str,
        subreddits: List[str] = None,
        time_filter: str = "month",  # hour, day, week, month, year, all
        limit: int = 10
    ) -> List[SearchSource]:
        """
        Search Reddit discussions

        Args:
            query: Search query
            subreddits: List of subreddits to search (None = all)
            time_filter: Time period
            limit: Number of results

        Returns:
            List of posts with comments
        """
        if not self.reddit:
            print("Reddit not initialized")
            return []

        results = []

        try:
            import concurrent.futures

            def search_sync():
                try:
                    if subreddits:
                        search_target = '+'.join(subreddits)
                    else:
                        search_target = "all"

                    search_results = []

                    for submission in self.reddit.subreddit(search_target).search(
                        query,
                        time_filter=time_filter,
                        limit=limit,
                        sort='relevance'
                    ):
                        # Get top comments
                        submission.comments.replace_more(limit=0)
                        top_comments = [
                            {
                                'author': comment.author.name if comment.author else '[deleted]',
                                'score': comment.score,
                                'body': comment.body,
                                'created': datetime.fromtimestamp(comment.created_utc)
                            }
                            for comment in submission.comments[:5]
                        ]

                        # Calculate credibility score based on score and subreddit
                        score_normalized = min(1.0, submission.score / 1000)
                        subreddit_multiplier = 1.0

                        # Popular subreddits get higher credibility
                        popular_subs = ['science', 'technology', 'programming', 'MachineLearning', 'AskScience']
                        if any(sub in submission.subreddit.display_name for sub in popular_subs):
                            subreddit_multiplier = 1.2

                        credibility_score = min(1.0, score_normalized * subreddit_multiplier)

                        result = SearchSource(
                            title=submission.title,
                            url=f"https://reddit.com{submission.permalink}",
                            snippet=submission.selftext[:300] + '...' if len(submission.selftext) > 300 else submission.selftext,
                            source_type=SourceType.REDDIT,
                            source_name=f"r/{submission.subreddit.display_name}",
                            published_date=datetime.fromtimestamp(submission.created_utc),
                            credibility_score=credibility_score,
                            relevance_score=0.7,  # Reddit results are conversational
                            content=submission.selftext,
                            metadata={
                                'subreddit': submission.subreddit.display_name,
                                'author': submission.author.name if submission.author else '[deleted]',
                                'score': submission.score,
                                'num_comments': submission.num_comments,
                                'top_comments': top_comments,
                                'flair': submission.link_flair_text,
                                'upvote_ratio': submission.upvote_ratio
                            }
                        )
                        search_results.append(result)

                    return search_results

                except Exception as e:
                    print(f"Reddit search failed: {e}")
                    return []

            # Run in thread pool to avoid blocking
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(search_sync)
                results = future.result(timeout=30)

        except Exception as e:
            print(f"Reddit search error: {e}")
            results = []

        return results

    async def search_twitter(
        self,
        query: str,
        limit: int = 10
    ) -> List[SearchSource]:
        """
        Search Twitter (using Twitter API or nitter)

        Note: Requires Twitter API access or use nitter.net
        """
        results = []

        try:
            # Try Twitter API first
            if self.twitter_bearer_token:
                results = await self._search_twitter_api(query, limit)
            else:
                # Fallback to web scraping (nitter)
                results = await self._search_twitter_web(query, limit)

        except Exception as e:
            print(f"Twitter search failed: {e}")
            results = []

        return results

    async def _search_twitter_api(
        self,
        query: str,
        limit: int
    ) -> List[SearchSource]:
        """Search Twitter using official API"""
        try:
            import tweepy

            # This would require Twitter API v2
            # For now, return empty list
            print("Twitter API v2 implementation needed")
            return []

        except ImportError:
            print("tweepy not available")
            return []

    async def _search_twitter_web(
        self,
        query: str,
        limit: int
    ) -> List[SearchSource]:
        """Search Twitter using web scraping (nitter.net)"""
        try:
            import aiohttp

            # Use nitter.net (Twitter proxy)
            url = f"https://nitter.net/search"
            params = {
                'q': query,
                'src': 'typed_query',
                'f': 'tweets'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return []

                    html = await response.text()

                    # Parse HTML (this is simplified - would need proper HTML parsing)
                    results = self._parse_nitter_html(html, limit)
                    return results

        except Exception as e:
            print(f"Nitter search failed: {e}")
            return []

    def _parse_nitter_html(self, html: str, limit: int) -> List[SearchSource]:
        """Parse nitter HTML results (simplified)"""
        # This would require beautifulsoup4 and proper HTML parsing
        # For now, return empty list
        return []

    def get_reddit_trending(self, subreddit: str = "all") -> List[Dict]:
        """Get trending topics from Reddit"""
        if not self.reddit:
            return []

        try:
            import concurrent.futures

            def get_trending_sync():
                results = []

                for submission in self.reddit.subreddit(subreddit).hot(limit=10):
                    results.append({
                        'title': submission.title,
                        'score': submission.score,
                        'subreddit': submission.subreddit.display_name,
                        'url': f"https://reddit.com{submission.permalink}",
                        'num_comments': submission.num_comments,
                        'created': datetime.fromtimestamp(submission.created_utc)
                    })

                return results

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(get_trending_sync)
                return future.result(timeout=10)

        except Exception as e:
            print(f"Reddit trending failed: {e}")
            return []

    async def search_hacker_news(
        self,
        query: str,
        limit: int = 10
    ) -> List[SearchSource]:
        """
        Search Hacker News

        Returns discussions from news.ycombinator.com
        """
        try:
            import aiohttp

            # Use Algolia HN Search API
            url = "https://hn.algolia.com/api/v1/search"
            params = {
                'query': query,
                'tags': 'story',
                'hitsPerPage': limit
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()

                    results = []
                    for hit in data.get('hits', []):
                        # Calculate credibility score based on points and comments
                        points = hit.get('points', 0)
                        num_comments = hit.get('num_comments', 0)

                        # HN scoring: points + comments indicate quality
                        credibility_score = min(1.0, (points + num_comments) / 500)

                        result = SearchSource(
                            title=hit.get('title', ''),
                            url=hit.get('url', ''),
                            snippet=hit.get('_highlightResult', {}).get('title', {}).get('value', ''),
                            source_type=SourceType.REDDIT,  # Close enough
                            source_name="Hacker News",
                            published_date=datetime.fromtimestamp(hit.get('created_at_i', 0)),
                            credibility_score=credibility_score,
                            relevance_score=0.75,
                            content=hit.get('title', ''),
                            metadata={
                                'author': hit.get('author'),
                                'points': points,
                                'num_comments': num_comments,
                                'hn_url': f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                            }
                        )
                        results.append(result)

                    return results

        except Exception as e:
            print(f"Hacker News search failed: {e}")
            return []

    async def search_social_all(
        self,
        query: str,
        limit: int = 8
    ) -> List[SearchSource]:
        """
        Search all social platforms simultaneously

        Returns combined results from Reddit, Twitter, HN
        """
        tasks = []

        # Reddit search
        if self.reddit:
            tasks.append(self.search_reddit(query, limit=limit//3))

        # Twitter search
        tasks.append(self.search_twitter(query, limit=limit//3))

        # Hacker News search
        tasks.append(self.search_hacker_news(query, limit=limit//3))

        # Run all searches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        all_results = []
        for result in results:
            if isinstance(result, list):
                all_results.extend(result)
            elif isinstance(result, Exception):
                print(f"Social search failed: {result}")

        # Sort by credibility and relevance
        all_results.sort(key=lambda x: x.credibility_score * x.relevance_score, reverse=True)

        return all_results[:limit]

    def get_social_trending(self) -> List[Dict]:
        """Get trending topics across social platforms"""
        trending = []

        # Reddit trending
        reddit_trending = self.get_reddit_trending()
        trending.extend([{
            'platform': 'reddit',
            'title': item['title'],
            'url': item['url'],
            'engagement': item['score'],
            'source': f"r/{item['subreddit']}"
        } for item in reddit_trending])

        # Could add Twitter trending, etc.

        # Sort by engagement
        trending.sort(key=lambda x: x.get('engagement', 0), reverse=True)

        return trending[:10]