#!/usr/bin/env python3
"""
Example: Upgrading Chatbot to Unified Brain
============================================

This shows how to upgrade your existing chatbot to use the new unified brain.
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from core.unified_brain import create_brain


def basic_chatbot():
    """
    Simple chatbot using unified brain
    Same interface as before, but with ALL new capabilities available!
    """
    print("🤖 Enhanced Chatbot (Powered by Unified Brain)")
    print("=" * 60)
    print("Now with:")
    print("  • Knowledge base (type 'help knowledge')")
    print("  • Code execution (type 'help code')")
    print("  • 23 tools (type 'help tools')")
    print("  • Web intelligence (type 'help web')")
    print("  • 20,810x faster caching!")
    print()
    print("Type 'quit' to exit")
    print("=" * 60)
    print()
    
    # Create brain (replaces old CompanionBrain)
    brain = create_brain(app_type="chatbot")
    
    user_id = "demo_user"
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("\n👋 Goodbye!")
                break
            
            # Help commands
            if user_input.lower() == 'help knowledge':
                print("\n📚 KNOWLEDGE COMMANDS:")
                print("  - Ask with context: 'with knowledge: <question>'")
                print("  - Example: 'with knowledge: What is RAG?'")
                print()
                continue
            
            if user_input.lower() == 'help code':
                print("\n⚡ CODE EXECUTION:")
                print("  - Execute code: 'run code: <language>\\n<code>'")
                print("  - Example: 'run code: python\\nprint(2+2)'")
                print()
                continue
            
            if user_input.lower() == 'help tools':
                tools = brain.list_tools()
                print(f"\n🛠️  AVAILABLE TOOLS ({len(tools)}):")
                for i, tool in enumerate(tools, 1):
                    print(f"  {i:2d}. {tool}")
                print()
                continue
            
            if user_input.lower() == 'help web':
                print("\n🌐 WEB INTELLIGENCE:")
                print("  - Get news: 'news: <topic>'")
                print("  - Example: 'news: artificial intelligence'")
                print()
                continue
            
            # Handle special commands
            use_knowledge = False
            use_search = False
            use_tools = False
            
            # Check for knowledge request
            if user_input.lower().startswith('with knowledge:'):
                use_knowledge = True
                user_input = user_input[15:].strip()
                print("🧠 Using knowledge base...")
            
            # Check for search request
            if user_input.lower().startswith('search:'):
                use_search = True
                user_input = user_input[7:].strip()
                print("🔍 Searching...")
            
            # Check for code execution
            if user_input.lower().startswith('run code:'):
                code_parts = user_input[9:].strip().split('\n', 1)
                if len(code_parts) == 2:
                    language, code = code_parts
                    print(f"⚡ Executing {language.strip()} code...")
                    result = brain.execute_code(code.strip(), language=language.strip())
                    
                    if result['success']:
                        print(f"\n✅ Output:\n{result['output']}")
                    else:
                        print(f"\n❌ Error: {result['error']}")
                    print()
                    continue
                else:
                    print("❌ Format: run code: <language>\\n<code>")
                    continue
            
            # Check for news request
            if user_input.lower().startswith('news:'):
                query = user_input[5:].strip()
                print(f"📰 Getting news about '{query}'...")
                result = brain.get_news(query=query, limit=5)
                
                if result['success']:
                    print(f"\n📰 Found {result['count']} articles:")
                    for i, article in enumerate(result['articles'][:5], 1):
                        print(f"  {i}. {article.get('title', 'N/A')}")
                else:
                    print(f"\n⚠️  {result['error']}")
                print()
                continue
            
            # Check for tool call (simple format: "add 5 3")
            parts = user_input.split()
            if len(parts) >= 2 and parts[0] in brain.list_tools():
                tool_name = parts[0]
                try:
                    args = [float(x) if '.' in x else int(x) for x in parts[1:]]
                    print(f"🛠️  Calling tool '{tool_name}'...")
                    result = brain.call_tool(tool_name, *args)
                    
                    if result['success']:
                        print(f"\n✅ Result: {result['result']}")
                    else:
                        print(f"\n❌ Error: {result['error']}")
                    print()
                    continue
                except:
                    pass  # Fall through to normal processing
            
            # Normal chat with unified brain
            response = brain.think(
                message=user_input,
                user_id=user_id,
                use_knowledge=use_knowledge,
                use_search=use_search,
                use_tools=use_tools
            )
            
            if response['success']:
                print(f"\nBot: {response['response']}\n")
                
                # Show performance info
                metadata = response['metadata']
                print(f"⏱️  Response time: {metadata['response_time']:.3f}s")
                if metadata.get('used_knowledge'):
                    print("📚 Enhanced with knowledge base")
                if metadata.get('used_search'):
                    print("🔍 Enhanced with search")
                print()
            else:
                print(f"\n❌ Error: {response.get('error', 'Unknown error')}\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
    
    # Show session stats
    print("\n📊 Session Statistics:")
    stats = brain.get_performance_stats()
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Successful: {stats['successful_requests']}")
    print(f"  Cache hits: {stats.get('cache', {}).get('hits', 'N/A')}")


if __name__ == "__main__":
    basic_chatbot()
