#!/bin/bash

# PyAMA Frontend Development Startup Script

echo "🚀 Starting PyAMA Frontend Development Environment"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Please run this script from the pyama-frontend directory"
    exit 1
fi

# Check if backend is running
echo "🔍 Checking if PyAMA Backend is running..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is running on http://localhost:8000"
else
    echo "⚠️  Backend is not running. Please start it with:"
    echo "   cd ../pyama-backend"
    echo "   uv run python -m pyama_backend"
    echo ""
    echo "   The frontend will still start, but you'll see connection errors."
fi

echo ""
echo "🌐 Starting Next.js development server..."
echo "   Frontend will be available at: http://0.0.0.0:3000 (and http://localhost:3000)"
echo "   Backend should be running at: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the development server"
echo ""

# Start the development server
npm run dev