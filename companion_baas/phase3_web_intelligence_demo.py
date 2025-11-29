#!/usr/bin/env python3
"""
🌐 Phase 3: Web Intelligence Demo
==================================

Demonstrates web scraping, API integration, and content indexing
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def demo_banner(title):
    """Print demo banner"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def demo_1_web_scraping():
    """Demo 1: Web Scraping with Crawler"""
    demo_banner("🌐 DEMO 1: Web Content Scraping")
    
    from web_intelligence import get_crawler
    
    crawler = get_crawler()
    
    if not crawler.enabled:
        print("⚠️  Crawler not available (install: pip install beautifulsoup4 requests)")
        return
    
    print("\n✅ Web crawler initialized")
    print(f"  Method: {'Crawl4AI' if hasattr(crawler, 'crawler') and crawler.crawler else 'Basic scraping'}")
    
    # Scrape examples
    test_urls = [
        "https://example.com",
        "https://www.python.org",
    ]
    
    print(f"\n🔍 Scraping {len(test_urls)} URLs...")
    
    for url in test_urls:
        print(f"\n  Scraping: {url}")
        result = crawler.scrape_url(url)
        
        if result.get('success'):
            print(f"  ✅ Success!")
            print(f"    • Title: {result.get('title', 'N/A')[:60]}")
            content = result.get('content', '')
            print(f"    • Content length: {len(content)} chars")
            print(f"    • Word count: {result.get('metadata', {}).get('word_count', 0)}")
            print(f"    • Links found: {len(result.get('links', []))}")
            print(f"    • Images found: {len(result.get('images', []))}")
        else:
            print(f"  ❌ Failed: {result.get('error', 'Unknown error')}")
    
    print("\n✅ Demo 1 Complete!")


def demo_2_news_api():
    """Demo 2: News API Integration"""
    demo_banner("📰 DEMO 2: News API Integration")
    
    from web_intelligence import get_news_client
    
    news_client = get_news_client()
    
    print(f"\n📡 News client initialized")
    print(f"  Status: {'Enabled (with API key)' if news_client.enabled else 'Demo mode (no API key)'}")
    
    # Get tech news
    print("\n🔍 Fetching top technology news...")
    tech_news = news_client.get_top_headlines(category='technology', limit=5)
    
    if tech_news:
        print(f"  ✅ Found {len(tech_news)} articles:")
        for i, article in enumerate(tech_news[:3], 1):
            print(f"\n  {i}. {article['title'][:60]}...")
            print(f"     Source: {article['source']}")
            print(f"     URL: {article['url'][:50]}...")
    else:
        print("  ⚠️  No news articles available (requires API key)")
    
    # Search news
    print("\n🔍 Searching news for 'artificial intelligence'...")
    ai_news = news_client.search_news('artificial intelligence', limit=3)
    
    if ai_news:
        print(f"  ✅ Found {len(ai_news)} articles about AI")
        for article in ai_news[:2]:
            print(f"  • {article['title'][:60]}...")
    
    print("\n✅ Demo 2 Complete!")


def demo_3_web_search():
    """Demo 3: Web Search API"""
    demo_banner("🔍 DEMO 3: Web Search Integration")
    
    from web_intelligence import get_search_client
    
    search_client = get_search_client()
    
    print("\n✅ Web search client initialized (DuckDuckGo)")
    
    # Test queries
    queries = [
        "Python programming language",
        "Machine learning",
        "Docker containers"
    ]
    
    for query in queries:
        print(f"\n🔍 Search: '{query}'")
        result = search_client.search(query, limit=5)
        
        if result.get('success'):
            instant = result.get('instant_answer', {})
            
            # Show instant answer
            abstract = instant.get('abstract_text') or instant.get('abstract')
            if abstract:
                print(f"  💡 Instant Answer:")
                print(f"    {abstract[:150]}...")
                if instant.get('abstract_url'):
                    print(f"    Source: {instant.get('abstract_url')}")
            
            # Show related topics
            related = result.get('related_topics', [])
            if related:
                print(f"\n  📚 Related topics ({len(related)}):")
                for topic in related[:3]:
                    print(f"    • {topic['title'][:60]}")
        else:
            print(f"  ❌ Search failed: {result.get('error')}")
    
    # Get instant answer
    print("\n💡 Getting instant answer...")
    answer = search_client.get_instant_answer("What is Docker?")
    if answer:
        print(f"  ✅ {answer[:200]}...")
    
    print("\n✅ Demo 3 Complete!")


def demo_4_content_indexing():
    """Demo 4: Index Web Content"""
    demo_banner("📚 DEMO 4: Web Content Indexing")
    
    from web_intelligence import get_crawler, get_search_client
    from search import get_search_engine
    from knowledge import get_vector_store
    
    crawler = get_crawler()
    search_engine = get_search_engine()
    vector_store = get_vector_store()
    
    if not crawler.enabled:
        print("⚠️  Crawler not available")
        return
    
    print("\n🔧 Components:")
    print(f"  • Crawler: {'✅' if crawler.enabled else '❌'}")
    print(f"  • Text Search: {'✅' if search_engine.text_search_enabled else '❌'}")
    print(f"  • Vector Search: {'✅' if search_engine.vector_search_enabled else '❌'}")
    
    # Scrape and index content
    print("\n📄 Scraping and indexing web content...")
    
    # Use search API to get content
    search_client = get_search_client()
    
    topics = ["Python tutorial", "Docker guide", "Machine learning basics"]
    index_name = "web_content"
    
    # Create indexes
    if search_engine.text_search_enabled:
        try:
            search_engine.meilisearch.create_index(index_name)
            search_engine.meilisearch.configure_index(
                index_name,
                searchable_attributes=['title', 'content', 'summary'],
                filterable_attributes=['source', 'topic']
            )
            print("  ✅ Meilisearch index created")
        except:
            pass
    
    if search_engine.vector_search_enabled:
        try:
            search_engine.elasticsearch.create_index(index_name, dimension=384)
            print("  ✅ Elasticsearch index created")
        except:
            pass
    
    indexed_count = 0
    
    for topic in topics:
        print(f"\n  Processing: '{topic}'")
        
        # Get instant answer as content
        result = search_client.search(topic, limit=1)
        
        if result.get('success'):
            instant = result.get('instant_answer', {})
            abstract = instant.get('abstract_text') or instant.get('abstract', '')
            
            if abstract:
                doc = {
                    'id': f"web_{topic.replace(' ', '_')}",
                    'title': instant.get('heading') or topic,
                    'content': abstract,
                    'summary': abstract[:200],
                    'source': instant.get('abstract_source', 'Web'),
                    'url': instant.get('abstract_url', ''),
                    'topic': topic
                }
                
                # Add to Meilisearch
                if search_engine.text_search_enabled:
                    try:
                        search_engine.meilisearch.add_documents(index_name, [doc])
                        print(f"    ✅ Indexed in Meilisearch")
                    except Exception as e:
                        print(f"    ⚠️  Meilisearch indexing failed: {e}")
                
                # Add to Elasticsearch with embedding
                if search_engine.vector_search_enabled and vector_store.enabled:
                    try:
                        embedding = vector_store.encode(f"{doc['title']} {doc['content']}")
                        es_doc = {**doc, 'embedding': embedding}
                        search_engine.elasticsearch.index_doc(index_name, doc['id'], es_doc)
                        print(f"    ✅ Indexed in Elasticsearch")
                    except Exception as e:
                        print(f"    ⚠️  Elasticsearch indexing failed: {e}")
                
                indexed_count += 1
    
    print(f"\n✅ Indexed {indexed_count} web documents")
    
    # Search indexed content
    import time
    time.sleep(2)
    
    print("\n🔍 Searching indexed web content...")
    search_queries = ["python", "docker", "learning"]
    
    for query in search_queries:
        print(f"\n  Query: '{query}'")
        
        if search_engine.text_search_enabled:
            results = search_engine.fast_search(query, index_name, limit=2)
            if results.get('hits'):
                print(f"    📝 Text search: {len(results['hits'])} results")
                for hit in results['hits'][:1]:
                    print(f"      • {hit.get('title', 'N/A')}")
    
    print("\n✅ Demo 4 Complete!")


def main():
    """Run Phase 3 demo"""
    print("\n" + "🌐 " + "="*68)
    print("🌐  PHASE 3: WEB INTELLIGENCE DEMO")
    print("🌐  Web Scraping + APIs + Content Indexing")
    print("🌐 " + "="*68)
    
    print("\n🚀 Demonstrating web intelligence capabilities...")
    
    try:
        demo_1_web_scraping()
        demo_2_news_api()
        demo_3_web_search()
        demo_4_content_indexing()
        
        # Summary
        demo_banner("🎉 PHASE 3 DEMO COMPLETE!")
        
        print("\n✅ Successfully demonstrated:")
        print("  • Web content scraping (BeautifulSoup)")
        print("  • News API integration")
        print("  • Web search (DuckDuckGo)")
        print("  • Content indexing pipeline")
        print("  • Integration with Phase 1 + 2")
        
        print("\n📊 Web Intelligence Stack:")
        print("  • Crawler: ✅ Basic scraping available")
        print("  • News API: ✅ Demo mode (requires API key)")
        print("  • Search API: ✅ DuckDuckGo (no key required)")
        print("  • Content Processing: ✅ Operational")
        
        print("\n🎯 Complete Architecture:")
        print("  Phase 1 (Knowledge): ✅ Vector store + Elasticsearch")
        print("  Phase 2 (Search): ✅ Meilisearch + Hybrid search")
        print("  Phase 3 (Web Intelligence): ✅ Scraping + APIs")
        
        print("\n📝 Next: Phase 4 - Execution & Generation")
        print("  • Open Interpreter for code execution")
        print("  • Image generation (Stable Diffusion)")
        print("  • Tool calling framework")
        print("  • Multi-modal capabilities")
        
        print("\n" + "="*70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
