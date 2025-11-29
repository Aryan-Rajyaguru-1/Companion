# Phase 3: Web Intelligence Layer

## Overview
Enables the Companion Brain to interact with the web through scraping, automation, and API integration.

## Components

### 1. Crawl4AI Integration
**Purpose**: Advanced web scraping with JavaScript execution and dynamic content handling

**Features**:
- JavaScript rendering
- Dynamic content scraping
- Anti-bot detection bypass
- Structured data extraction
- Screenshot capture

**Use Cases**:
- Extract product information from e-commerce sites
- Scrape news articles and blog posts
- Monitor website changes
- Collect structured data (JSON-LD, Schema.org)

### 2. Browser-Use Automation
**Purpose**: Browser automation for complex web interactions

**Features**:
- Full browser automation
- Click, type, scroll interactions
- Multi-step workflows
- Cookie management
- Session persistence

**Use Cases**:
- Login to websites
- Fill out forms
- Navigate multi-page workflows
- Extract data requiring authentication
- Automated testing

### 3. Public APIs Integration
**Purpose**: Connect to external services and data sources

**Integrated APIs**:
- **News APIs**: Real-time news from various sources
- **Weather APIs**: Current and forecast weather data
- **Financial APIs**: Stock prices, crypto, market data
- **Social Media APIs**: Twitter, Reddit trends
- **Search APIs**: DuckDuckGo, Google Custom Search
- **Knowledge APIs**: Wikipedia, Wikidata

## Architecture

```
web_intelligence/
├── __init__.py              # Module exports
├── crawler.py               # Crawl4AI wrapper
├── browser_automation.py    # Browser-Use wrapper
├── api_clients/             # Public API clients
│   ├── __init__.py
│   ├── news_api.py          # News sources
│   ├── weather_api.py       # Weather data
│   ├── finance_api.py       # Financial data
│   ├── search_api.py        # Web search
│   └── social_api.py        # Social media trends
└── content_processor.py     # Process and index web content

```

## Integration with Phase 1 & 2

**Content Pipeline**:
1. **Fetch** (Phase 3): Scrape/crawl web content
2. **Process** (Phase 3): Extract, clean, structure data
3. **Embed** (Phase 1): Generate vector embeddings
4. **Index** (Phase 2): Store in Meilisearch + Elasticsearch
5. **Search** (Phase 2): Fast text + semantic search
6. **Cache** (Phase 1): Redis for frequently accessed data

**Example Flow**:
```python
# 1. Scrape website
crawler = get_crawler()
content = crawler.scrape_url("https://example.com/article")

# 2. Process content
processor = ContentProcessor()
structured_data = processor.extract_article(content)

# 3. Generate embedding
vector_store = get_vector_store()
embedding = vector_store.encode(structured_data['text'])

# 4. Index in both search backends
search_engine = get_search_engine()
search_engine.index_document(
    index_name="web_content",
    doc_id=structured_data['url'],
    document={
        **structured_data,
        'embedding': embedding
    }
)

# 5. Now searchable via fast text or semantic search!
```

## Installation

```bash
# Install web intelligence dependencies
pip install crawl4ai playwright beautifulsoup4 requests

# Install browser (required for Crawl4AI)
playwright install chromium
```

## Configuration

Add to `config.py`:

```python
@dataclass
class Crawl4AIConfig:
    enabled: bool = True
    browser: str = "chromium"  # chromium, firefox, webkit
    headless: bool = True
    timeout: int = 30000  # milliseconds
    max_retries: int = 3
    user_agent: str = "Mozilla/5.0..."

@dataclass
class APIConfig:
    # News API
    news_api_key: Optional[str] = None
    
    # Weather API
    weather_api_key: Optional[str] = None
    
    # Financial API
    finance_api_key: Optional[str] = None
    
    # Rate limits
    max_requests_per_minute: int = 60
    cache_ttl: int = 300  # seconds
```

## Next Steps

1. **Implement Crawl4AI Wrapper**
   - Basic scraping
   - JavaScript execution
   - Screenshot capture
   - Content extraction

2. **Implement API Clients**
   - News API integration
   - Weather API integration
   - Financial data APIs
   - Search APIs

3. **Content Processing Pipeline**
   - Text extraction and cleaning
   - Metadata extraction
   - Automatic categorization
   - Deduplication

4. **Integration Testing**
   - Scrape and index workflow
   - API fetch and cache
   - Search indexed web content
   - Real-world scenarios

5. **Demo Application**
   - Web content search engine
   - News aggregator
   - Weather dashboard
   - Price tracker
