#!/usr/bin/env python3
"""
Advanced Search Engine Wrapper
Combines multiple free search engines and web scraping for comprehensive data mining
"""

import requests
import json
import urllib.parse
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import concurrent.futures
import threading
from dataclasses import dataclass
import hashlib

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """Structured search result data"""
    title: str
    url: str
    snippet: str
    source: str
    timestamp: datetime
    relevance_score: float = 0.0
    content: str = ""
    meta_data: Dict[str, Any] = None

class MultiSearchEngineWrapper:
    """Advanced wrapper for multiple search engines with data mining capabilities"""
    
    def __init__(self):
        self.cache = {}
        self.cache_expiry = timedelta(hours=2)  # Cache results for 2 hours
        
        # Create session with connection pooling for better performance
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=2,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        self.rate_limits = {
            'duckduckgo': {'last_call': 0, 'min_interval': 0.5},  # Reduced from 1.0
            'searx': {'last_call': 0, 'min_interval': 0.3},  # Reduced from 0.5
            'google_custom': {'last_call': 0, 'min_interval': 1.0},  # Reduced from 1.5
            'bing': {'last_call': 0, 'min_interval': 0.5},  # Reduced from 1.0
            'startpage': {'last_call': 0, 'min_interval': 1.0},  # Reduced from 2.0
            'qwant': {'last_call': 0, 'min_interval': 0.5},  # Reduced from 1.0
            'mojeek': {'last_call': 0, 'min_interval': 0.8},  # Reduced from 1.5
            'brave': {'last_call': 0, 'min_interval': 0.5},  # Reduced from 1.0
            'yep': {'last_call': 0, 'min_interval': 0.8}  # Reduced from 1.5
        }
        
        # User agents for rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        # SearX instances (public, no API key needed)
        self.searx_instances = [
            'https://searx.be',
            'https://search.sapti.me',
            'https://searx.xyz',
            'https://searx.prvcy.eu',
            'https://search.mdosch.de',
            'https://searx.work',
            'https://searx.tiekoetter.com'
        ]
        
        # Additional free search engines
        self.brave_api_key = ""  # Optional: Get free key from https://brave.com/search/api/
        self.qwant_enabled = True  # Qwant API (no key needed for basic)
        self.mojeek_enabled = True  # Mojeek API (independent search engine)
    
    def _get_cache_key(self, query: str, engine: str) -> str:
        """Generate cache key for query and engine"""
        return hashlib.md5(f"{query}_{engine}".encode()).hexdigest()
    
    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """Check if cache entry is still valid"""
        return datetime.now() - timestamp < self.cache_expiry
    
    def _respect_rate_limit(self, engine: str):
        """Respect rate limits for different engines"""
        if engine in self.rate_limits:
            last_call = self.rate_limits[engine]['last_call']
            min_interval = self.rate_limits[engine]['min_interval']
            elapsed = time.time() - last_call
            
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)
            
            self.rate_limits[engine]['last_call'] = time.time()
    
    def _enhance_search_query(self, query: str) -> List[str]:
        """Enhanced query formulation for better relevance"""
        base_query = query.strip()
        enhanced_queries = [base_query]
        
        # For name queries, add context variations
        if any(pattern in query.lower() for pattern in ['who is', 'about ', 'tell me about']):
            name_part = query.lower().replace('who is ', '').replace('about ', '').replace('tell me about ', '').strip()
            
            # Add specific context variations for better results
            enhanced_queries.extend([
                f"{name_part} definition meaning",
                f"{name_part} wikipedia",
                f"{name_part} person biography",
                f"what does {name_part} mean",
                f"{name_part} history origin"
            ])
        
        # For technical queries, add variations
        elif any(word in query.lower() for word in ['quantum', 'computing', 'technology', 'programming']):
            enhanced_queries.extend([
                f"{base_query} explanation",
                f"{base_query} overview",
                f"what is {base_query}"
            ])
        
        return enhanced_queries[:3]  # Return top 3 variations
    
    def _calculate_relevance_score(self, result: SearchResult, query: str) -> float:
        """Calculate relevance score based on content quality and query match"""
        score = result.relevance_score
        
        # Boost score for authoritative sources
        authoritative_domains = ['wikipedia.org', 'britannica.com', 'merriam-webster.com', 
                               'dictionary.com', 'encyclopedia.com', 'academic.edu']
        if any(domain in result.url.lower() for domain in authoritative_domains):
            score += 0.2
        
        # Boost score for comprehensive content
        if result.snippet and len(result.snippet) > 200:
            score += 0.1
        
        # Boost score for exact query matches in title or snippet
        query_words = query.lower().split()
        title_lower = result.title.lower()
        snippet_lower = result.snippet.lower() if result.snippet else ""
        
        title_matches = sum(1 for word in query_words if word in title_lower)
        snippet_matches = sum(1 for word in query_words if word in snippet_lower)
        
        if title_matches > 0:
            score += (title_matches / len(query_words)) * 0.3
        if snippet_matches > 0:
            score += (snippet_matches / len(query_words)) * 0.2
        
        # Penalize very short snippets
        if result.snippet and len(result.snippet) < 50:
            score -= 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _get_headers(self) -> Dict[str, str]:
        """Get randomized headers"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'application/json, text/html, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive'
        }
    
    def search_duckduckgo(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using DuckDuckGo Instant Answer API"""
        self._respect_rate_limit('duckduckgo')
        
        try:
            # DuckDuckGo Instant Answer with reduced timeout
            url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
            response = self.session.get(url, headers=self._get_headers(), timeout=5)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = []
            
            # Process Abstract
            if data.get('AbstractText'):
                results.append(SearchResult(
                    title=data.get('AbstractSource', 'DuckDuckGo Abstract'),
                    url=data.get('AbstractURL', ''),
                    snippet=data.get('AbstractText', ''),
                    source='duckduckgo',
                    timestamp=datetime.now(),
                    relevance_score=0.9
                ))
            
            # Process Answer
            if data.get('Answer'):
                results.append(SearchResult(
                    title='Direct Answer',
                    url='',
                    snippet=data.get('Answer', ''),
                    source='duckduckgo',
                    timestamp=datetime.now(),
                    relevance_score=0.95
                ))
            
            # Process Related Topics
            for topic in data.get('RelatedTopics', [])[:max_results]:
                if isinstance(topic, dict) and topic.get('Text'):
                    results.append(SearchResult(
                        title=topic.get('Text', '').split(' - ')[0],
                        url=topic.get('FirstURL', ''),
                        snippet=topic.get('Text', ''),
                        source='duckduckgo',
                        timestamp=datetime.now(),
                        relevance_score=0.7
                    ))
            
            # Process Results
            for result in data.get('Results', [])[:max_results]:
                if isinstance(result, dict) and result.get('Text'):
                    results.append(SearchResult(
                        title=result.get('Text', '').split(' - ')[0],
                        url=result.get('FirstURL', ''),
                        snippet=result.get('Text', ''),
                        source='duckduckgo',
                        timestamp=datetime.now(),
                        relevance_score=0.8
                    ))
            
            return results[:max_results]
            
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return []
    
    def search_searx(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using SearXNG instances - metasearch aggregating multiple engines"""
        self._respect_rate_limit('searx')
        
        # Try all engines through SearXNG metasearch
        engine_combinations = [
            'google,bing,duckduckgo,qwant',  # Main 4 engines (faster)
            'google,bing,duckduckgo,qwant,mojeek,brave,yahoo',  # All 7 engines
            'google,bing,duckduckgo',  # Fallback to top 3
        ]
        
        # Try only first 3 instances for speed
        for instance in self.searx_instances[:3]:
            for engines in engine_combinations:
                try:
                    url = f"{instance}/search"
                    params = {
                        'q': query,
                        'format': 'json',
                        'engines': engines,
                        'safesearch': '0',
                        'categories': 'general'
                    }
                    
                    # Shorter timeout for faster response
                    response = self.session.get(url, params=params, headers=self._get_headers(), timeout=4)
                    
                    if response.status_code != 200:
                        continue
                    
                    data = response.json()
                    results = []
                    
                    for result in data.get('results', [])[:max_results]:
                        results.append(SearchResult(
                            title=result.get('title', ''),
                            url=result.get('url', ''),
                            snippet=result.get('content', '') or result.get('snippet', ''),
                            source=f"searx_{result.get('engine', 'unknown')}",
                            timestamp=datetime.now(),
                            relevance_score=0.80
                        ))
                    
                    if results:
                        logger.info(f"✅ SearXNG ({instance.split('//')[1]}): {len(results)} results from engines: {engines}")
                        return results
                        
                except Exception as e:
                    logger.debug(f"SearX {instance.split('//')[1] if '//' in instance else instance} failed: {str(e)[:80]}")
                    continue
        
        return []
    
    def search_startpage(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using Startpage (privacy-focused Google results)"""
        self._respect_rate_limit('startpage')
        
        try:
            # Startpage search (scraping approach)
            url = "https://www.startpage.com/sp/search"
            params = {
                'query': query,
                'lang': 'english',
                'rcount': max_results
            }
            
            response = requests.get(url, params=params, headers=self._get_headers(), timeout=15)
            
            if response.status_code != 200 or not BS4_AVAILABLE:
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Parse search results
            for result_div in soup.find_all('div', class_='w-gl__result')[:max_results]:
                title_elem = result_div.find('h3')
                link_elem = result_div.find('a')
                snippet_elem = result_div.find('p', class_='w-gl__description')
                
                if title_elem and link_elem:
                    results.append(SearchResult(
                        title=title_elem.get_text(strip=True),
                        url=link_elem.get('href', ''),
                        snippet=snippet_elem.get_text(strip=True) if snippet_elem else '',
                        source='startpage',
                        timestamp=datetime.now(),
                        relevance_score=0.85
                    ))
            
            return results
            
        except Exception as e:
            logger.warning(f"Startpage search failed: {e}")
            return []
    
    def search_bing_free(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using Bing (free tier/scraping)"""
        self._respect_rate_limit('bing')
        
        try:
            # Bing search URL
            url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count={max_results}"
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            
            if response.status_code != 200 or not BS4_AVAILABLE:
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Parse Bing results
            for result in soup.find_all('li', class_='b_algo')[:max_results]:
                title_elem = result.find('h2')
                link_elem = title_elem.find('a') if title_elem else None
                snippet_elem = result.find('div', class_='b_caption')
                
                if title_elem and link_elem:
                    snippet_text = ''
                    if snippet_elem:
                        snippet_text = snippet_elem.get_text(strip=True)
                    
                    results.append(SearchResult(
                        title=title_elem.get_text(strip=True),
                        url=link_elem.get('href', ''),
                        snippet=snippet_text,
                        source='bing',
                        timestamp=datetime.now(),
                        relevance_score=0.8
                    ))
            
            return results
            
        except Exception as e:
            logger.warning(f"Bing search failed: {e}")
            return []
    
    def search_qwant(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using Qwant (privacy-focused, no API key needed)"""
        try:
            self._respect_rate_limit('qwant')
            
            # Try API first
            url = f"https://api.qwant.com/v3/search/web"
            params = {
                'q': query,
                'count': max_results,
                'locale': 'en_US',
                'device': 'desktop'
            }
            
            headers = self._get_headers()
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            results = []
            if response.status_code == 200:
                try:
                    data = response.json()
                    items = data.get('data', {}).get('result', {}).get('items', [])
                    
                    for item in items[:max_results]:
                        results.append(SearchResult(
                            title=item.get('title', ''),
                            url=item.get('url', ''),
                            snippet=item.get('desc', ''),
                            source='qwant',
                            timestamp=datetime.now(),
                            relevance_score=0.8
                        ))
                    
                    if results:
                        return results
                except:
                    pass
            
            # Fallback to web scraping if API fails
            if not results and BS4_AVAILABLE:
                scrape_url = f"https://www.qwant.com/?q={urllib.parse.quote(query)}&t=web"
                response = requests.get(scrape_url, headers=self._get_headers(), timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    # Try to extract any links from the page
                    for link in soup.find_all('a', href=True)[:max_results]:
                        href = link.get('href', '')
                        if href.startswith('http') and 'qwant.com' not in href:
                            title = link.get_text(strip=True)
                            if title and len(title) > 10:
                                results.append(SearchResult(
                                    title=title[:200],
                                    url=href,
                                    snippet='',
                                    source='qwant',
                                    timestamp=datetime.now(),
                                    relevance_score=0.7
                                ))
            
            return results
            
        except Exception as e:
            logger.debug(f"Qwant search failed: {e}")
            return []
    
    def search_mojeek(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using Mojeek (independent search engine, no tracking)"""
        try:
            self._respect_rate_limit('mojeek')
            
            # Mojeek search URL (web scraping)
            url = f"https://www.mojeek.com/search"
            params = {'q': query}
            
            headers = self._get_headers()
            response = requests.get(url, params=params, headers=headers, timeout=12)
            
            results = []
            if response.status_code == 200 and BS4_AVAILABLE:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try multiple selectors for Mojeek results
                search_results = (soup.find_all('li', class_='result') or 
                                soup.find_all('div', class_='results-standard') or
                                soup.find_all('article') or
                                soup.find_all('li', class_='result-item'))
                
                for item in search_results[:max_results]:
                    # Try multiple ways to find title and URL
                    title_elem = (item.find('a', class_='title') or 
                                 item.find('h2') or 
                                 item.find('a'))
                    snippet_elem = (item.find('p', class_='s') or 
                                   item.find('p', class_='snippet') or
                                   item.find('p'))
                    
                    if title_elem and title_elem.get('href'):
                        results.append(SearchResult(
                            title=title_elem.get_text(strip=True)[:200],
                            url=title_elem.get('href', ''),
                            snippet=snippet_elem.get_text(strip=True)[:300] if snippet_elem else '',
                            source='mojeek',
                            timestamp=datetime.now(),
                            relevance_score=0.75
                        ))
            
            return results
            
        except Exception as e:
            logger.debug(f"Mojeek search failed: {e}")
            return []
    
    def search_brave(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using Brave Search API (free tier available)"""
        if not self.brave_api_key:
            logger.debug("Brave API key not configured, skipping")
            return []
        
        try:
            self._respect_rate_limit('brave')
            
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.brave_api_key
            }
            params = {
                "q": query,
                "count": max_results,
                "search_lang": "en"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            results = []
            if response.status_code == 200:
                data = response.json()
                web_results = data.get('web', {}).get('results', [])
                
                for item in web_results[:max_results]:
                    results.append(SearchResult(
                        title=item.get('title', ''),
                        url=item.get('url', ''),
                        snippet=item.get('description', ''),
                        source='Brave Search',
                        timestamp=datetime.now(),
                        relevance_score=0.85
                    ))
            
            return results
            
        except Exception as e:
            logger.warning(f"Brave search failed: {e}")
            return []
    
    def search_yep(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using Yep (Ahrefs search engine, privacy-focused)"""
        try:
            self._respect_rate_limit('yep')
            
            # Yep search (web scraping) - updated selectors
            url = "https://yep.com/web"
            params = {'q': query}
            headers = self._get_headers()
            headers['User-Agent'] = random.choice(self.user_agents)
            
            response = requests.get(url, params=params, headers=headers, timeout=12)
            
            results = []
            if response.status_code == 200 and BS4_AVAILABLE:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try multiple selectors for Yep results
                search_results = (soup.find_all('div', class_='result') or
                                soup.find_all('div', class_='search-result') or
                                soup.find_all('article') or
                                soup.select('div[data-testid*="result"]'))
                
                for item in search_results[:max_results]:
                    # Try multiple ways to find links
                    title_elem = (item.find('a', class_='result-link') or 
                                 item.find('h3') and item.find('h3').find('a') or
                                 item.find('a', href=True))
                    snippet_elem = (item.find('p', class_='snippet') or
                                   item.find('p') or
                                   item.find('div', class_='description'))
                    
                    if title_elem and title_elem.get('href'):
                        href = title_elem.get('href', '')
                        # Ensure it's a valid URL
                        if href.startswith('http'):
                            results.append(SearchResult(
                                title=title_elem.get_text(strip=True)[:200],
                                url=href,
                                snippet=snippet_elem.get_text(strip=True)[:300] if snippet_elem else '',
                                source='yep',
                                timestamp=datetime.now(),
                                relevance_score=0.75
                        ))
            
            return results
            
        except Exception as e:
            logger.warning(f"Yep search failed: {e}")
            return []
    
    def scrape_content(self, url: str, max_length: int = 2000) -> str:
        """Enhanced content scraping from URLs - optimized"""
        if not BS4_AVAILABLE:
            return "Content scraping requires BeautifulSoup4"
        
        try:
            # Use session with reduced timeout
            response = self.session.get(url, headers=self._get_headers(), timeout=5)
            
            if response.status_code != 200:
                return f"Failed to fetch content (Status: {response.status_code})"
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                element.decompose()
            
            # Try to find main content areas
            main_content = None
            content_selectors = [
                'main', 'article', '.content', '.main-content', 
                '.post-content', '.entry-content', '#content', 
                '.container', '.wrapper'
            ]
            
            for selector in content_selectors:
                main_content = soup.select_one(selector)
                if main_content:
                    break
            
            if not main_content:
                main_content = soup.find('body')
            
            if main_content:
                # Extract text content
                text = main_content.get_text(separator=' ', strip=True)
                
                # Clean up text
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                clean_text = ' '.join(chunk for chunk in chunks if chunk and len(chunk) > 10)
                
                # Truncate if needed
                if len(clean_text) > max_length:
                    clean_text = clean_text[:max_length] + "..."
                
                return clean_text
            
            return "No readable content found"
            
        except Exception as e:
            return f"Error scraping content: {str(e)}"
    
    def multi_engine_search(self, query: str, max_results: int = 20, include_content: bool = True) -> List[SearchResult]:
        """Search across multiple engines concurrently with enhanced relevance"""
        cache_key = self._get_cache_key(query, 'multi')
        
        # Check cache first
        if cache_key in self.cache:
            cached_result, timestamp = self.cache[cache_key]
            if self._is_cache_valid(timestamp):
                logger.info(f"🎯 Using cached results for: {query}")
                return cached_result
        
        logger.info(f"🔍 Multi-engine search for: {query}")
        
        # Generate enhanced queries for better relevance
        search_queries = self._enhance_search_query(query)
        primary_query = search_queries[0]
        
        all_results = []
        search_functions = [
            self.search_duckduckgo,
            self.search_searx,
            self.search_startpage,
            self.search_bing_free,
            self.search_qwant,
            self.search_mojeek,
            self.search_yep
        ]
        
        # Add Brave if API key configured
        if self.brave_api_key:
            search_functions.append(self.search_brave)
        
        # Search with primary query first - use fewer workers for faster response
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_engine = {
                executor.submit(func, primary_query, max_results//len(search_functions)): func.__name__ 
                for func in search_functions
            }
            
            # Wait for all futures with faster timeout - continue with partial results if some timeout
            try:
                for future in concurrent.futures.as_completed(future_to_engine, timeout=8):
                    engine_name = future_to_engine[future]
                    try:
                        # Reduced timeout for faster failure
                        results = future.result(timeout=3)
                        # Recalculate relevance scores
                        for result in results:
                            result.relevance_score = self._calculate_relevance_score(result, query)
                        all_results.extend(results)
                        logger.info(f"✅ {engine_name}: {len(results)} results")
                        
                        # Early exit if we have enough good results
                        if len(all_results) >= max_results // 2:
                            logger.info(f"🎯 Got {len(all_results)} results, stopping early")
                            break
                    except concurrent.futures.TimeoutError:
                        logger.debug(f"⏱️ {engine_name} timed out")
                    except Exception as e:
                        logger.debug(f"❌ {engine_name} failed: {str(e)[:100]}")
            except concurrent.futures.TimeoutError:
                # Some engines didn't finish in time, but use whatever results we got
                logger.info(f"⏱️ Search timeout reached, continuing with {len(all_results)} results from completed engines")
        
        # If we have few results, try HTML fallback first
        if len(all_results) < 3:
            logger.info("🔧 Trying HTML fallback for basic results")
            try:
                html_results = self.simple_html_search(primary_query, max_results=10)
                for result in html_results:
                    result.relevance_score = self._calculate_relevance_score(result, query)
                all_results.extend(html_results)
            except Exception as e:
                logger.warning(f"HTML fallback failed: {e}")
        
        # If still no results, try Wikipedia/direct sources as last resort
        if len(all_results) == 0:
            logger.info("🔍 Trying direct Wikipedia search as last resort")
            try:
                wiki_results = self.search_wikipedia_fallback(primary_query, max_results=5)
                for result in wiki_results:
                    result.relevance_score = self._calculate_relevance_score(result, query)
                all_results.extend(wiki_results)
                logger.info(f"✅ Wikipedia fallback: {len(wiki_results)} results")
            except Exception as e:
                logger.warning(f"Wikipedia fallback failed: {e}")
        
        # If we still have few results, try alternative queries
        if len(all_results) < 5 and len(search_queries) > 1:
            logger.info("🔄 Trying alternative queries for better coverage")
            for alt_query in search_queries[1:]:
                try:
                    # Try DuckDuckGo with alternative query
                    alt_results = self.search_duckduckgo(alt_query, 3)
                    for result in alt_results:
                        result.relevance_score = self._calculate_relevance_score(result, query)
                    all_results.extend(alt_results)
                    if len(all_results) >= 8:  # Stop if we have enough results
                        break
                except Exception as e:
                    logger.warning(f"Alternative query failed: {e}")
        
        # Remove duplicates based on URL and title similarity
        unique_results = self._deduplicate_results(all_results)
        
        # Sort by relevance score (highest first)
        unique_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Limit results
        final_results = unique_results[:max_results]
        
        # Scrape content for top results if requested
        if include_content and BS4_AVAILABLE:
            self._scrape_content_parallel(final_results[:5])  # Scrape top 5
        if include_content and BS4_AVAILABLE:
            self._scrape_content_parallel(final_results[:5])  # Scrape top 5
        
        # Cache results
        self.cache[cache_key] = (final_results, datetime.now())
        
        logger.info(f"📊 Multi-search complete: {len(final_results)} unique results")
        return final_results
    
    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results based on URL and title similarity"""
        seen_urls = set()
        seen_titles = set()
        unique_results = []
        
        for result in results:
            # Skip if URL already seen
            if result.url and result.url in seen_urls:
                continue
            
            # Skip if title is very similar to one already seen
            title_lower = result.title.lower()
            is_similar = any(
                self._similarity_ratio(title_lower, seen_title) > 0.8 
                for seen_title in seen_titles
            )
            
            if not is_similar:
                unique_results.append(result)
                if result.url:
                    seen_urls.add(result.url)
                seen_titles.add(title_lower)
        
        return unique_results
    
    def _similarity_ratio(self, str1: str, str2: str) -> float:
        """Calculate similarity ratio between two strings"""
        if not str1 or not str2:
            return 0.0
        
        # Simple similarity based on common words
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        if not words1 or not words2:
            return 0.0
        
        common_words = words1.intersection(words2)
        total_words = words1.union(words2)
        
        return len(common_words) / len(total_words)
    
    def _scrape_content_parallel(self, results: List[SearchResult]):
        """Scrape content from multiple URLs in parallel - optimized with faster timeout"""
        def scrape_single(result):
            if result.url:
                try:
                    result.content = self.scrape_content(result.url, max_length=1000)  # Reduced from 1500
                except:
                    result.content = ""  # Fail silently
        
        # Reduced workers and timeout for faster response
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(scrape_single, result) for result in results[:3] if result.url]  # Only top 3
            concurrent.futures.wait(futures, timeout=10)  # Reduced from 30
    
    def enhanced_search_with_mining(self, query: str, deep_search: bool = False) -> Dict[str, Any]:
        """Comprehensive search with data mining capabilities"""
        logger.info(f"🚀 Enhanced search with mining for: {query}")
        
        # Basic multi-engine search
        results = self.multi_engine_search(query, max_results=15, include_content=True)
        
        # Extract key information
        extracted_data = {
            'query': query,
            'total_results': len(results),
            'sources': list(set(r.source for r in results)),
            'results': results,
            'summary': self._generate_summary(results),
            'key_facts': self._extract_key_facts(results),
            'related_topics': self._extract_related_topics(results),
            'source_urls': [r.url for r in results if r.url],
            'timestamp': datetime.now().isoformat()
        }
        
        if deep_search:
            # Additional mining for deep search
            extracted_data.update(self._deep_mining(query, results))
        
        return extracted_data
    
    def _generate_summary(self, results: List[SearchResult]) -> str:
        """Generate a summary from search results"""
        if not results:
            return "No results found"
        
        # Combine snippets and content
        all_text = []
        for result in results[:5]:  # Top 5 results
            if result.snippet:
                all_text.append(result.snippet)
            if result.content:
                all_text.append(result.content[:300])  # First 300 chars of content
        
        combined_text = ' '.join(all_text)
        
        # Simple extractive summary (first 500 characters with complete sentences)
        if len(combined_text) > 500:
            truncated = combined_text[:500]
            last_period = truncated.rfind('.')
            if last_period > 200:  # Ensure we have substantial content
                return truncated[:last_period + 1]
        
        return combined_text[:500] + "..." if len(combined_text) > 500 else combined_text
    
    def _extract_key_facts(self, results: List[SearchResult]) -> List[str]:
        """Extract key facts from search results"""
        facts = []
        
        for result in results:
            text = f"{result.snippet} {result.content}".strip()
            if len(text) < 50:
                continue
            
            # Look for fact-like sentences (containing numbers, dates, or specific patterns)
            sentences = text.split('.')
            for sentence in sentences:
                sentence = sentence.strip()
                if (len(sentence) > 30 and len(sentence) < 200 and
                    (any(char.isdigit() for char in sentence) or
                     any(word in sentence.lower() for word in ['founded', 'established', 'created', 'developed', 'invented', 'discovered']))):
                    facts.append(sentence + '.')
        
        return list(set(facts))[:10]  # Return unique facts, max 10
    
    def _extract_related_topics(self, results: List[SearchResult]) -> List[str]:
        """Extract related topics from search results"""
        topics = set()
        
        for result in results:
            # Extract potential topics from titles and snippets
            text = f"{result.title} {result.snippet}".lower()
            
            # Simple topic extraction (look for capitalized phrases)
            words = text.split()
            for i, word in enumerate(words):
                if i < len(words) - 1:
                    two_word = f"{words[i]} {words[i+1]}"
                    if (len(two_word) > 5 and len(two_word) < 30 and
                        not any(char.isdigit() for char in two_word)):
                        topics.add(two_word.title())
        
        return list(topics)[:15]  # Max 15 topics
    
    def _deep_mining(self, query: str, results: List[SearchResult]) -> Dict[str, Any]:
        """Perform deep mining for additional insights"""
        logger.info(f"🔬 Deep mining for: {query}")
        
        deep_data = {
            'content_analysis': {},
            'source_credibility': {},
            'temporal_data': [],
            'technical_details': []
        }
        
        # Analyze content depth and quality
        for result in results:
            if result.content:
                content_score = min(len(result.content) / 1000, 1.0)  # Normalize to 0-1
                deep_data['content_analysis'][result.source] = {
                    'content_length': len(result.content),
                    'quality_score': content_score,
                    'has_technical_content': any(word in result.content.lower() 
                                               for word in ['algorithm', 'protocol', 'implementation', 'architecture'])
                }
        
        return deep_data
    
    def simple_html_search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Simple HTML-based search fallback when APIs fail"""
        logger.info(f"🔧 Using simple HTML scraper for: {query}")
        results = []
        
        try:
            # Use HTML.com search engine with basic scraping
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            response = self.session.get(search_url, headers=self._get_headers(), timeout=5)
            
            if response.status_code == 200 and BS4_AVAILABLE:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find result links
                for link in soup.find_all('a', class_='result__a', limit=max_results):
                    title = link.get_text(strip=True)
                    url = link.get('href', '')
                    
                    # Find snippet
                    snippet = ""
                    snippet_elem = link.find_next('a', class_='result__snippet')
                    if snippet_elem:
                        snippet = snippet_elem.get_text(strip=True)
                    
                    if title and url:
                        results.append(SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            source='duckduckgo_html',
                            timestamp=datetime.now(),
                            relevance_score=0.6
                        ))
                
                logger.info(f"✅ HTML scraper found {len(results)} results")
        except Exception as e:
            logger.warning(f"HTML scraper failed: {str(e)}")
        
        return results
    
    def search_wikipedia_fallback(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Wikipedia API fallback - reliable and doesn't require API key"""
        logger.info(f"� Wikipedia fallback search for: {query}")
        results = []
        
        try:
            # Wikipedia API search
            api_url = "https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'opensearch',
                'search': query,
                'limit': max_results,
                'namespace': 0,
                'format': 'json'
            }
            
            # Wikipedia requires a proper User-Agent
            headers = {
                'User-Agent': 'CompanionAI/1.0 (Educational; contact@companion.ai) Python-Requests',
                'Accept': 'application/json'
            }
            
            response = requests.get(api_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # OpenSearch returns: [query, [titles], [descriptions], [urls]]
                if len(data) >= 4:
                    titles, descriptions, urls = data[1], data[2], data[3]
                    
                    for i in range(min(len(titles), max_results)):
                        if i < len(urls):
                            results.append(SearchResult(
                                title=titles[i],
                                url=urls[i],
                                snippet=descriptions[i] if i < len(descriptions) else "",
                                source='wikipedia',
                                timestamp=datetime.now(),
                                relevance_score=0.9  # Wikipedia is usually very relevant for "Who is" queries
                            ))
                    
                    logger.info(f"✅ Wikipedia found {len(results)} results")
            
            # If Wikipedia search succeeds, also try to get a summary
            if results:
                # Get summary for the first result
                summary_params = {
                    'action': 'query',
                    'prop': 'extracts',
                    'exintro': True,
                    'explaintext': True,
                    'titles': results[0].title,
                    'format': 'json'
                }
                
                summary_response = requests.get(api_url, params=summary_params, headers=headers, timeout=10)
                if summary_response.status_code == 200:
                    summary_data = summary_response.json()
                    pages = summary_data.get('query', {}).get('pages', {})
                    for page_id, page_data in pages.items():
                        extract = page_data.get('extract', '')
                        if extract:
                            # Add the summary as content to the first result
                            results[0].content = extract[:500]  # First 500 chars
                            logger.info(f"✅ Got Wikipedia summary ({len(extract)} chars)")
                
        except Exception as e:
            logger.warning(f"Wikipedia search failed: {str(e)}")
        
        return results

# Global instance
search_wrapper = MultiSearchEngineWrapper()
