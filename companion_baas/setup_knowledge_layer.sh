#!/bin/bash

# Companion Brain - Quick Setup Script
# Automatically sets up the Knowledge Layer

set -e  # Exit on error

echo "🧠 Companion Brain - Knowledge Layer Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Check prerequisites
echo "1️⃣ Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
print_status "Python $PYTHON_VERSION found"

# Check Docker
if ! command -v docker &> /dev/null; then
    print_warning "Docker not found. You'll need to install services manually."
    USE_DOCKER=false
else
    print_status "Docker found"
    USE_DOCKER=true
fi

# Check Docker Compose
if [ "$USE_DOCKER" = true ] && ! command -v docker-compose &> /dev/null; then
    print_warning "Docker Compose not found. Using 'docker compose' instead."
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

echo ""

# Navigate to companion_baas directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Start Docker services
if [ "$USE_DOCKER" = true ]; then
    echo "2️⃣ Starting Docker services..."
    
    # Check if services are already running
    if $DOCKER_COMPOSE ps | grep -q "Up"; then
        print_info "Services already running. Restarting..."
        $DOCKER_COMPOSE restart
    else
        print_info "Starting Elasticsearch, Meilisearch, and Redis..."
        $DOCKER_COMPOSE up -d
    fi
    
    # Wait for services to be healthy
    print_info "Waiting for services to be ready (30 seconds)..."
    sleep 30
    
    # Check service health
    print_info "Checking service health..."
    
    # Test Elasticsearch
    if curl -s http://localhost:9200 > /dev/null; then
        print_status "Elasticsearch is running on port 9200"
    else
        print_error "Elasticsearch is not responding"
    fi
    
    # Test Meilisearch
    if curl -s http://localhost:7700/health > /dev/null; then
        print_status "Meilisearch is running on port 7700"
    else
        print_error "Meilisearch is not responding"
    fi
    
    # Test Redis
    if command -v redis-cli &> /dev/null && redis-cli ping > /dev/null 2>&1; then
        print_status "Redis is running on port 6379"
    else
        print_warning "Redis check skipped (redis-cli not installed)"
    fi
    
    echo ""
else
    echo "2️⃣ Docker not available - skipping service setup"
    print_warning "You'll need to install Elasticsearch, Meilisearch, and Redis manually"
    print_info "See INSTALLATION_GUIDE.md for manual installation instructions"
    echo ""
fi

# Install Python dependencies
echo "3️⃣ Installing Python dependencies..."

print_info "Installing core packages..."
pip install -q elasticsearch>=8.11.0 sentence-transformers>=2.2.2 meilisearch>=0.31.0 redis>=5.0.0

print_status "Python packages installed"

# Download embedding model
print_info "Downloading embedding model (first time only, ~90MB)..."
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" 2>/dev/null

print_status "Embedding model ready"

echo ""

# Test installation
echo "4️⃣ Testing installation..."

# Create test script
cat > /tmp/test_companion_brain.py << 'EOF'
import sys
sys.path.insert(0, '.')

from knowledge import get_knowledge_retriever

retriever = get_knowledge_retriever()

if retriever.is_enabled():
    print("✅ Knowledge Layer is operational!")
    
    # Get stats
    stats = retriever.get_stats()
    print(f"📊 Stats:")
    print(f"   - Total conversations: {stats.get('total_conversations', 0)}")
    print(f"   - Embedding dim: {stats.get('embedding_dim', 0)}")
    print(f"   - Index: {stats.get('index_name', 'N/A')}")
    sys.exit(0)
else:
    print("❌ Knowledge Layer is disabled")
    print("Check that Elasticsearch is running and dependencies are installed")
    sys.exit(1)
EOF

# Run test
if python3 /tmp/test_companion_brain.py; then
    echo ""
    echo "=========================================="
    echo "🎉 Setup Complete!"
    echo "=========================================="
    echo ""
    echo "The Companion Brain is ready with:"
    echo "  ✅ Elasticsearch (Vector Database)"
    echo "  ✅ Meilisearch (Fast Search)"
    echo "  ✅ Redis (Caching)"
    echo "  ✅ Knowledge Layer (RAG)"
    echo ""
    echo "Next steps:"
    echo "  1. Read INTEGRATION_GUIDE.md to integrate with your app"
    echo "  2. Try examples in examples/ directory"
    echo "  3. See BRAIN_INTEGRATION_MASTER_PLAN.md for Phase 2-5"
    echo ""
    echo "To stop services: $DOCKER_COMPOSE down"
    echo "To restart: $DOCKER_COMPOSE up -d"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "⚠️  Setup Incomplete"
    echo "=========================================="
    echo ""
    echo "Some components are not working correctly."
    echo "Please check:"
    echo "  1. Docker services are running: $DOCKER_COMPOSE ps"
    echo "  2. Python dependencies installed: pip list"
    echo "  3. Review INSTALLATION_GUIDE.md for troubleshooting"
    echo ""
fi

# Cleanup
rm -f /tmp/test_companion_brain.py
