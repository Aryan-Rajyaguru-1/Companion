"""
Web Crawler using Crawl4AI
===========================

Advanced web scraping with JavaScript execution and dynamic content handling
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import re

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

logger = logging.getLogger(__name__)


class WebContentCrawler:
    """
    Web crawler for extracting content from websites
    
    Features:
    - JavaScript rendering
    - Dynamic content scraping
    - Structured data extraction
    - Clean text extraction
    - Metadata extraction
    """
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize web crawler
        
        Args:
            headless: Run browser in headless mode
            timeout: Page load timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
        self.enabled = False
        
        if not CRAWL4AI_AVAILABLE:
            logger.warning("Crawl4AI not installed. Run: pip install crawl4ai")
            logger.info("Falling back to basic scraping if available")
            self.crawler = None
            # Enable if we have beautifulsoup for fallback
            self.enabled = BS4_AVAILABLE
            return
        
        try:
            # Initialize Crawl4AI async crawler
            # Note: AsyncWebCrawler is used asynchronously, we'll create it on demand
            self.crawler = None  # Will be created async when needed
            self.browser_config = BrowserConfig(
                headless=headless,
                verbose=False
            )
            self.enabled = True
            logger.info("✅ Web crawler initialized (async mode)")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize crawler: {e}")
            self.crawler = None
            self.enabled = BS4_AVAILABLE  # Fallback to basic scraping
    
    def scrape_url(self, url: str, wait_for: Optional[str] = None) -> Dict[str, Any]:
        """
        Scrape content from a URL
        
        Args:
            url: URL to scrape
            wait_for: CSS selector to wait for before scraping
            
        Returns:
            Dictionary with scraped content and metadata
        """
        if not self.enabled:
            logger.error("Crawler not available")
            return {'success': False, 'error': 'Crawler not available'}
        
        try:
            if CRAWL4AI_AVAILABLE:
                # Use Crawl4AI (async mode - run synchronously for now)
                import asyncio
                
                async def _crawl():
                    async with AsyncWebCrawler(config=self.browser_config) as crawler:
                        result = await crawler.arun(
                            url=url,
                            config=CrawlerRunConfig(
                                word_count_threshold=10,
                                cache_mode="bypass"
                            )
                        )
                        return result
                
                # Run async function synchronously
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                result = loop.run_until_complete(_crawl())
                
                if result.success:
                    return {
                        'success': True,
                        'url': url,
                        'title': self._extract_title(result.html),
                        'content': result.markdown or result.cleaned_html or result.html,
                        'html': result.html,
                        'links': result.links.get('external', [])[:20] if hasattr(result.links, 'get') else [],
                        'images': result.media.get('images', [])[:10] if hasattr(result.media, 'get') else [],
                        'timestamp': datetime.utcnow().isoformat(),
                        'metadata': {
                            'word_count': len(result.markdown.split()) if result.markdown else 0,
                            'has_javascript': True
                        }
                    }
                else:
                    return {
                        'success': False,
                        'error': result.error_message,
                        'url': url
                    }
            
            else:
                # Fallback to basic requests + BeautifulSoup
                return self._scrape_basic(url)
                
        except Exception as e:
            logger.error(f"❌ Failed to scrape {url}: {e}")
            return {
                'success': False,
                'error': str(e),
                'url': url
            }
    
    def _scrape_basic(self, url: str) -> Dict[str, Any]:
        """
        Basic scraping fallback using requests + BeautifulSoup
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary with scraped content
        """
        if not BS4_AVAILABLE:
            return {'success': False, 'error': 'BeautifulSoup not available'}
        
        try:
            import requests
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = soup.find('title')
            title_text = title.get_text().strip() if title else 'No title'
            
            # Remove script and style tags
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            # Extract main content
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            content_text = main_content.get_text(separator='\n', strip=True) if main_content else ''
            
            # Clean up text
            content_text = re.sub(r'\n\s*\n', '\n\n', content_text)
            
            # Extract links
            links = [a.get('href') for a in soup.find_all('a', href=True)][:20]
            
            # Extract images
            images = [img.get('src') for img in soup.find_all('img', src=True)][:10]
            
            return {
                'success': True,
                'url': url,
                'title': title_text,
                'content': content_text,
                'html': str(soup),
                'links': links,
                'images': images,
                'timestamp': datetime.utcnow().isoformat(),
                'metadata': {
                    'word_count': len(content_text.split()),
                    'has_javascript': False,
                    'method': 'basic'
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Basic scraping failed for {url}: {e}")
            return {
                'success': False,
                'error': str(e),
                'url': url
            }
    
    def _extract_title(self, html: str) -> str:
        """Extract title from HTML"""
        if not html:
            return "No title"
        
        if BS4_AVAILABLE:
            try:
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.find('title')
                return title.get_text().strip() if title else "No title"
            except:
                pass
        
        # Fallback regex
        import re
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        return match.group(1) if match else "No title"
    
    async def scrape_url_async(self, url: str) -> Dict[str, Any]:
        """
        Async version for better performance with threads
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary with scraped content
        """
        if not CRAWL4AI_AVAILABLE:
            return self._scrape_basic(url)
        
        try:
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=url,
                    config=CrawlerRunConfig(
                        word_count_threshold=10,
                        cache_mode="bypass"
                    )
                )
                
                if result.success:
                    return {
                        'success': True,
                        'url': url,
                        'title': self._extract_title(result.html),
                        'content': result.markdown or result.cleaned_html or result.html,
                        'html': result.html,
                        'links': result.links.get('external', [])[:20] if hasattr(result.links, 'get') else [],
                        'images': result.media.get('images', [])[:10] if hasattr(result.media, 'get') else [],
                        'timestamp': datetime.utcnow().isoformat()
                    }
                return {'success': False, 'error': result.error_message}
        except Exception as e:
            logger.error(f"Async scrape failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def scrape_multiple(self, urls: List[str], max_concurrent: int = 3) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs concurrently
        
        Args:
            urls: List of URLs to scrape
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of scraping results
        """
        results = []
        
        for url in urls:
            result = self.scrape_url(url)
            results.append(result)
        
        return results
    
    def extract_article(self, url: str) -> Dict[str, Any]:
        """
        Extract article content with better formatting
        
        Args:
            url: URL of article
            
        Returns:
            Article data with clean content
        """
        result = self.scrape_url(url)
        
        if not result.get('success'):
            return result
        
        # Additional processing for articles
        content = result.get('content', '')
        
        # Extract first paragraph as summary (up to 200 chars)
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 50]
        summary = paragraphs[0][:200] + '...' if paragraphs else ''
        
        return {
            **result,
            'summary': summary,
            'article_type': 'article',
            'content_type': 'text/html'
        }
    
    def close(self):
        """Clean up crawler resources"""
        if self.crawler and hasattr(self.crawler, 'close'):
            try:
                self.crawler.close()
            except:
                pass


# Singleton instance
_crawler_instance = None

def get_crawler() -> WebContentCrawler:
    """Get singleton crawler instance"""
    global _crawler_instance
    if _crawler_instance is None:
        _crawler_instance = WebContentCrawler()
    return _crawler_instance
