#!/bin/bash
# Start Companion BaaS Production Stack

echo "
================================================================================
  🐳 STARTING COMPANION BAAS PRODUCTION STACK
================================================================================
"

cd "$(dirname "$0")"

echo "📍 Working directory: $(pwd)"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    echo "   Run: sudo systemctl start docker"
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Check if docker-compose file exists
if [ ! -f "docker-compose.production.yml" ]; then
    echo "❌ docker-compose.production.yml not found!"
    exit 1
fi

echo "✅ Found docker-compose.production.yml"
echo ""

echo "🚀 Starting services (this may take a few minutes)..."
echo "   - API Service (Companion BaaS)"
echo "   - Elasticsearch"
echo "   - Meilisearch"
echo "   - Redis"
echo "   - Nginx"
echo "   - Prometheus"
echo "   - Grafana"
echo ""

# Start the stack
docker-compose -f docker-compose.production.yml up -d

# Check status
if [ $? -eq 0 ]; then
    echo ""
    echo "
================================================================================
  ✅ PRODUCTION STACK STARTED SUCCESSFULLY!
================================================================================

📊 SERVICE STATUS:
"
    docker-compose -f docker-compose.production.yml ps
    
    echo "
🌐 ACCESS POINTS:
   • API:           http://localhost:8000
   • API Docs:      http://localhost:8000/docs
   • Elasticsearch: http://localhost:9200
   • Meilisearch:   http://localhost:7700
   • Prometheus:    http://localhost:9090
   • Grafana:       http://localhost:3000

📋 USEFUL COMMANDS:
   • View logs:     docker-compose -f docker-compose.production.yml logs -f
   • Stop stack:    docker-compose -f docker-compose.production.yml down
   • Restart:       docker-compose -f docker-compose.production.yml restart
   • Status:        docker-compose -f docker-compose.production.yml ps

================================================================================
"
else
    echo ""
    echo "❌ Failed to start stack. Check the error messages above."
    exit 1
fi
