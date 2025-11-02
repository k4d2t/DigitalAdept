#!/bin/bash
# Quick start script for DataSec application

set -e

echo "🚀 Starting DataSec Application..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "✏️  Please edit .env file with your configuration"
    echo ""
fi

# Initialize database if needed
if [ ! -f "instance/datasec.db" ]; then
    echo "🗄️  Initializing database..."
    export FLASK_APP=wsgi.py
    export SECRET_KEY=${SECRET_KEY:-development-secret-key}
    
    if [ ! -d "migrations" ]; then
        flask db init
    fi
    
    flask db migrate -m "Initial migration" 2>/dev/null || true
    flask db upgrade
fi

# Run the application
echo ""
echo "✅ Setup complete!"
echo ""
echo "Starting development server on http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

export FLASK_APP=wsgi.py
export FLASK_ENV=development
export SECRET_KEY=${SECRET_KEY:-development-secret-key}

flask run
