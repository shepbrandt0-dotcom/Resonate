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

# Best-effort LAN IP so the demo can be opened from a phone on the same Wi-Fi
LAN_IP=$(python -c "
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    print(s.getsockname()[0])
    s.close()
except OSError:
    pass
" 2>/dev/null)

echo ""
echo "========================================"
echo "  Resonate is running"
echo "  On this computer : http://127.0.0.1:5000"
if [ -n "$LAN_IP" ]; then
echo "  On your phone     : http://$LAN_IP:5000  (same Wi-Fi)"
fi
echo "========================================"
echo ""
echo "  Demo client portal code : DEMO2026"
echo "  Admin password          : resonate2026"
echo ""
echo "  Open /demo or the admin dashboard for a QR code"
echo "  that opens the site straight from your phone."
echo ""
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

python app.py
