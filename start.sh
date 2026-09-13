#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "→ Setting up Resonate..."

# Prefer python3
PYTHON=python3
if ! command -v $PYTHON &>/dev/null; then
  PYTHON=python
fi

# Create venv if missing
if [ ! -d "venv" ]; then
  echo "→ Creating virtual environment..."
  $PYTHON -m venv venv
fi

# Activate
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

# Install
echo "→ Installing dependencies..."
pip install -q --upgrade pip
pip install -q flask

# Ensure data dir
mkdir -p data

# Init DB (idempotent)
python -c "from app import init_db; init_db(); print('→ Database ready')"

echo ""
echo "========================================"
echo "  Resonate is running"
echo "  Open: http://127.0.0.1:5000"
echo "========================================"
echo ""
echo "  Demo client portal code : DEMO2026"
echo "  Admin password          : resonate2026"
echo ""
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

python app.py
