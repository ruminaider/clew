#!/usr/bin/env bash
set -euo pipefail

# clew setup script — reduces 5 manual steps to one command.
# Usage: curl -sSL <url> | bash   OR   bash scripts/setup.sh

echo "=== clew setup ==="
echo ""

# Step 1: Check Python >=3.10
echo "Checking Python version..."
python3 -c "import sys; assert sys.version_info >= (3,10), f'Python 3.10+ required, got {sys.version}'" 2>/dev/null \
  || { echo "Error: Python 3.10+ required. Install from https://python.org/downloads/"; exit 1; }
echo "  Python $(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"

# Step 2: Install package
echo ""
echo "Installing clew..."
pip3 install clewdex

# Step 3: Check Docker + start Qdrant
echo ""
echo "Checking Docker..."
if ! docker info &>/dev/null; then
  echo "Error: Docker not running. Install Docker Desktop or start the daemon."
  echo "  macOS:  brew install --cask docker"
  echo "  Linux:  https://docs.docker.com/engine/install/"
  exit 1
fi

if ! curl -sf http://localhost:6333/ &>/dev/null; then
  echo "Starting Qdrant..."
  docker run -d --name clew-qdrant -p 6333:6333 \
    -v clew_qdrant_data:/qdrant/storage qdrant/qdrant:v1.16.1
  # Wait for health
  for i in {1..10}; do
    curl -sf http://localhost:6333/ &>/dev/null && break
    sleep 1
  done
  if ! curl -sf http://localhost:6333/ &>/dev/null; then
    echo "Error: Qdrant failed to start. Check: docker logs clew-qdrant"
    exit 1
  fi
  echo "  Qdrant started on localhost:6333"
else
  echo "  Qdrant already running on localhost:6333"
fi

# Step 4: Validate Voyage API key
echo ""
if [ -z "${VOYAGE_API_KEY:-}" ]; then
  echo "Enter your Voyage AI API key (get one free at https://dash.voyageai.com/):"
  read -r VOYAGE_API_KEY
  export VOYAGE_API_KEY
fi

echo "Validating Voyage API key..."
python3 -c "
import voyageai; c = voyageai.Client()
c.embed(['test'], model='voyage-code-3', input_type='document')
print('  Voyage API key validated.')
" || { echo "Error: Invalid VOYAGE_API_KEY. Get one at https://dash.voyageai.com/"; exit 1; }

# Step 5: Index current directory
echo ""
echo "Indexing $(pwd)..."
clew index . --full

# Step 6: Generate MCP config snippet
echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "Add to your Claude Code .mcp.json:"
echo ""
echo "  \"clew\": {"
echo "    \"command\": \"clew\","
echo "    \"args\": [\"serve\"],"
echo "    \"env\": {"
echo "      \"VOYAGE_API_KEY\": \"$VOYAGE_API_KEY\","
echo "      \"QDRANT_URL\": \"http://localhost:6333\""
echo "    }"
echo "  }"
echo ""
echo "Try it: clew search \"your query here\""
echo "Health: clew doctor"
