# Intelligent Caching System Documentation

## Overview
The Companion AI system now features an **Intelligent Caching System** that automatically detects time-sensitive queries and manages cache durations appropriately. This ensures that information like prices, technical specifications, current events, and other time-sensitive data is automatically updated from web sources.

## Key Features

### 🔍 **Automatic Web Search Detection**
The system automatically triggers web search for queries that likely contain outdated information:

- **Financial/Price Data**: Currency rates, stock prices, product costs, taxes, GST rates
- **Technical Specifications**: Product specs, dimensions, performance data
- **Current Events**: News, recent updates, today's information  
- **Weather/Environmental**: Current weather, air quality, forecasts
- **Legal/Regulatory**: Laws, policies, government regulations
- **Business Information**: Company data, earnings, market information

### ⏰ **Smart Cache Duration Management**

Different types of information get different cache durations:

| Category | Cache Duration | Use Cases |
|----------|----------------|-----------|
| **Financial** | 24 hours | Prices, exchange rates, tax rates |
| **Technical** | 7 days | Product specifications, technical details |
| **Current Events** | 1 hour | News, recent updates, breaking news |
| **Environmental** | 6 hours | Weather, air quality, forecasts |
| **Regulatory** | 30 days | Laws, regulations, policies |
| **Business** | 7 days | Company info, earnings, market data |

### 🧠 **Query Pattern Recognition**

The system recognizes patterns that indicate time-sensitive information:

```python
# Examples of automatically detected patterns:
"What is the current price of Bitcoin?"          # → Financial (24h cache)
"iPhone 15 Pro specifications"                   # → Technical (7d cache)  
"Latest news about AI developments"              # → Current Events (1h cache)
"Current weather in Mumbai"                      # → Environmental (6h cache)
"GST rate for electronics in India"             # → Financial (24h cache)
```

## Implementation Details

### **Automatic Web Search Triggering**

When you ask questions like:
- "What is the price of...?"
- "Current specifications of...?"  
- "Latest news about...?"
- "Today's exchange rate..."

The system will:
1. **Detect** the time-sensitive nature of the query
2. **Automatically enable** web search (even if not explicitly requested)
3. **Prioritize** web results over LLM knowledge for current information
4. **Cache** the results with an appropriate TTL

### **Smart Cache Management**

```python
# Cache entries are stored with:
{
    'query_key': (response, timestamp, ttl_seconds),
    'metadata': {
        'time_sensitive': True,
        'category': 'financial',
        'cache_duration': 86400  # 24 hours
    }
}
```

### **Cache Cleanup**

The system automatically:
- Removes expired cache entries
- Monitors memory usage
- Provides cache statistics
- Allows manual cache refresh for specific patterns

## Usage Examples

### **Automatic Detection (No Manual Tools Required)**

```python
# These queries automatically trigger web search:
"What is the current Bitcoin price?"
"iPhone 15 Pro Max specifications and price"
"Latest updates from OpenAI"
"Current USD to INR exchange rate"
"GST rate for software services in India"
```

### **Manual Cache Management**

```python
from api_wrapper import api_wrapper

# Get cache statistics
stats = api_wrapper.get_cache_statistics()
print(f"Total cache entries: {stats['total_entries']}")

# Clean expired entries  
expired_count = api_wrapper.cleanup_expired_cache()
print(f"Cleaned {expired_count} expired entries")

# Force refresh for price-related queries
refreshed = api_wrapper.force_cache_refresh_for_pattern("price")
print(f"Refreshed {refreshed} price-related cache entries")
```

## Configuration

### **Time-Sensitive Patterns**

You can modify the detection patterns in `api_wrapper.py`:

```python
self.time_sensitive_patterns = {
    'financial': {
        'patterns': ['price', 'cost', 'salary', 'wage', 'tax', 'gst', 'rate'],
        'cache_duration': 86400,  # 24 hours
        'description': 'Financial and pricing information'
    },
    # Add custom categories...
}
```

### **Cache Durations**

Adjust cache durations based on your needs:

```python
# Quick updates (1 hour)
'current_events': {'cache_duration': 3600}

# Daily updates (24 hours)  
'financial': {'cache_duration': 86400}

# Weekly updates (7 days)
'technical': {'cache_duration': 604800}
```

## Benefits

### 🎯 **Always Current Information**
- Prices, specifications, and current events are always up-to-date
- No more outdated information from LLM training data

### ⚡ **Performance Optimization**  
- Intelligent caching reduces redundant web searches
- Smart TTL management balances freshness with efficiency

### 🔍 **Seamless Experience**
- Users don't need to manually enable web search
- System automatically knows when current information is needed

### 💾 **Memory Efficient**
- Automatic cleanup of expired entries
- Configurable cache size limits
- Memory usage monitoring

## Testing

Run the test suite to see the system in action:

```bash
cd website
python3 test_intelligent_cache.py
```

This will demonstrate:
- Time-sensitive query detection
- Cache duration assignment
- Automatic web search triggering
- Cache statistics and management

## Real-World Examples

### **E-commerce Queries**
```
"iPhone 15 Pro price in India"
→ Detected: Financial category
→ Action: Auto web search enabled  
→ Cache: 24 hours
→ Result: Current prices from multiple sources
```

### **Technical Research**
```
"RTX 4090 specifications"
→ Detected: Technical category
→ Action: Auto web search enabled
→ Cache: 7 days  
→ Result: Latest technical specifications
```

### **Financial Information**
```
"Current GST rate for electronics"
→ Detected: Financial + Regulatory
→ Action: Auto web search enabled
→ Cache: 24 hours
→ Result: Current tax rates and regulations
```

The system ensures you always get the most current and accurate information for time-sensitive queries while maintaining excellent performance through intelligent caching.
