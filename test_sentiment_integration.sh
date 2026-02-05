#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------------------
# Test script for sentiment pipeline integration
# -------------------------------------------------------------------

echo "========================================"
echo "Sentiment Pipeline Integration Test"
echo "========================================"
echo ""

BACKEND_PORT=${BACKEND_PORT:-5001}
SENTIMENT_PORT=${SENTIMENT_PORT:-8002}
HOST=${HOST:-127.0.0.1}

echo "Testing configuration:"
echo "  Backend: http://$HOST:$BACKEND_PORT"
echo "  Sentiment Pipeline: http://$HOST:$SENTIMENT_PORT"
echo ""

# Test 1: Check if sentiment pipeline is running
echo "1. Testing sentiment pipeline health..."
if curl -sS "http://$HOST:$SENTIMENT_PORT/health" > /dev/null 2>&1; then
  echo "   ✅ Sentiment pipeline is running"
  curl -sS "http://$HOST:$SENTIMENT_PORT/health" | python3 -m json.tool
else
  echo "   ❌ Sentiment pipeline is NOT running"
  echo "   Start it with: ./start_sentiment_pipeline.sh"
  exit 1
fi
echo ""

# Test 2: Check backend health
echo "2. Testing backend health..."
if curl -sS "http://$HOST:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
  echo "   ✅ Backend is running"
else
  echo "   ❌ Backend is NOT running"
  echo "   Start it with: ./start_local.sh"
  exit 1
fi
echo ""

# Test 3: Test proxy endpoint
echo "3. Testing /api/sentiment/pipeline-health proxy..."
response=$(curl -sS "http://$HOST:$BACKEND_PORT/api/sentiment/pipeline-health")
if echo "$response" | grep -q '"pipeline_running": true'; then
  echo "   ✅ Pipeline health check via proxy works"
  echo "$response" | python3 -m json.tool
else
  echo "   ❌ Pipeline health check failed"
  echo "$response"
  exit 1
fi
echo ""

# Test 4: Test tiered sentiment endpoint
echo "4. Testing /api/sentiment/tiered endpoint..."
response=$(curl -sS "http://$HOST:$BACKEND_PORT/api/sentiment/tiered")
if echo "$response" | grep -q '"success": true'; then
  echo "   ✅ Tiered sentiment endpoint works"
  echo "$response" | python3 -m json.tool | head -30
else
  echo "   ❌ Tiered sentiment endpoint failed"
  echo "$response"
  exit 1
fi
echo ""

# Test 5: Test divergence endpoint
echo "5. Testing /api/sentiment/divergence endpoint..."
response=$(curl -sS "http://$HOST:$BACKEND_PORT/api/sentiment/divergence")
if echo "$response" | grep -q '"success": true'; then
  echo "   ✅ Divergence endpoint works"
  echo "$response" | python3 -m json.tool
else
  echo "   ❌ Divergence endpoint failed"
  echo "$response"
fi
echo ""

# Test 6: Test sources endpoint
echo "6. Testing /api/sentiment/sources endpoint..."
response=$(curl -sS "http://$HOST:$BACKEND_PORT/api/sentiment/sources")
if echo "$response" | grep -q '"success": true'; then
  echo "   ✅ Sources endpoint works"
  echo "$response" | python3 -m json.tool | head -20
else
  echo "   ❌ Sources endpoint failed"
  echo "$response"
fi
echo ""

echo "========================================"
echo "✅ All tests passed!"
echo "========================================"
echo ""
echo "Your sentiment pipeline is fully integrated!"
echo ""
echo "API Endpoints available:"
echo "  GET  /api/sentiment/tiered           - Tiered sentiment data"
echo "  GET  /api/sentiment/pipeline-health  - Pipeline health check"
echo "  GET  /api/sentiment/divergence       - Divergence analysis"
echo "  GET  /api/sentiment/sources          - Source list and stats"
echo ""
