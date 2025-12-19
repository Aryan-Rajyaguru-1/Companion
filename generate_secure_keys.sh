#!/bin/bash
# ===========================================
# COMPANION AI - SECURE KEY GENERATOR
# ===========================================
# This script generates secure random keys for your .env file
# Run this to populate JWT_SECRET, API_KEY, and SECRET_KEY

echo "🔐 Generating secure keys for Companion AI Framework..."
echo ""

# Generate JWT Secret (64 characters)
JWT_SECRET=$(openssl rand -hex 32)
echo "JWT_SECRET=$JWT_SECRET"

# Generate API Key (32 characters)
API_KEY=$(openssl rand -hex 16)
echo "API_KEY=$API_KEY"

# Generate Flask Secret Key (32 characters)
SECRET_KEY=$(openssl rand -hex 16)
echo "SECRET_KEY=$SECRET_KEY"

echo ""
echo "✅ Secure keys generated!"
echo ""
echo "📝 Copy these values to your .env file:"
echo "   JWT_SECRET=$JWT_SECRET"
echo "   API_KEY=$API_KEY"
echo "   SECRET_KEY=$SECRET_KEY"
echo ""
echo "⚠️  IMPORTANT: Keep these keys secure and never commit them to version control!"