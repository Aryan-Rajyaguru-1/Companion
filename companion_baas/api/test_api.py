#!/usr/bin/env python3
"""
Tests for Companion Brain API Server
"""

import pytest
from fastapi.testclient import TestClient
from .api_server import app, API_KEY

print(f"API_KEY in test: {API_KEY}")

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "Companion Brain API Server" in response.json()["message"]

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_chat_endpoint():
    # Test without API key (should fail)
    response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == 401

    # Test with API key
    headers = {"X-API-Key": API_KEY}
    response = client.post("/chat", json={"message": "Hello"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "role" in data
    assert "content" in data

def test_conversations_endpoint():
    headers = {"X-API-Key": API_KEY}
    
    # Create conversation
    response = client.post("/conversations", headers=headers)
    assert response.status_code == 200
    conv_id = response.json()["conversation_id"]
    
    # Get conversations
    response = client.get("/conversations", headers=headers)
    assert response.status_code == 200
    assert "conversations" in response.json()
    
    # Get specific conversation
    response = client.get(f"/conversations/{conv_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["conversation_id"] == conv_id

def test_streaming_endpoint():
    headers = {"X-API-Key": API_KEY}
    
    # Test streaming endpoint
    response = client.post("/chat/stream", json={"message": "Hello"}, headers=headers)
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    
    # For TestClient, we can check that it's a streaming response
    # The actual streaming content would be tested in integration tests
    content = response.text
    assert "data:" in content  # Should contain streaming data format

if __name__ == "__main__":
    pytest.main([__file__])