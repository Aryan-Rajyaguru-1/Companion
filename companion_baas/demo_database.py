#!/usr/bin/env python3
"""
Database Demo Script
Demonstrates conversation persistence functionality
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from core.database import db

def demo_database():
    print("🗄️  Companion AI Database Demo")
    print("=" * 40)

    # Create a conversation
    conv_id = "demo_conv_001"
    print(f"📝 Creating conversation: {conv_id}")
    conversation = db.create_conversation(conv_id, "Demo Conversation")
    print(f"✅ Created: {conversation}")

    # Add some messages
    print("\n💬 Adding messages...")
    messages = [
        {"id": "msg1", "role": "user", "type": "user", "content": "Hello AI!", "timestamp": "2024-01-01T10:00:00"},
        {"id": "msg2", "role": "assistant", "type": "assistant", "content": "Hello! How can I help you?", "timestamp": "2024-01-01T10:00:01"},
        {"id": "msg3", "role": "user", "type": "user", "content": "Tell me about databases", "timestamp": "2024-01-01T10:00:02"},
    ]

    for msg in messages:
        db.add_message(conv_id, msg)
        print(f"✅ Added: {msg['role']} - {msg['content'][:30]}...")

    # Retrieve conversation
    print(f"\n📖 Retrieving conversation: {conv_id}")
    retrieved = db.get_conversation(conv_id)
    if retrieved:
        print(f"📊 Conversation has {len(retrieved['messages'])} messages")
        for msg in retrieved['messages']:
            print(f"  {msg['role']}: {msg['content']}")

    # List all conversations
    print("\n📋 All conversations:")
    conversations = db.get_all_conversations()
    for conv in conversations:
        print(f"  {conv['id']}: {conv['message_count']} messages")

    # Clean up
    print(f"\n🗑️  Deleting conversation: {conv_id}")
    db.delete_conversation(conv_id)
    print("✅ Deleted")

    print("\n🎉 Database demo completed successfully!")

if __name__ == "__main__":
    demo_database()