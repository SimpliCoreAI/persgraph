#!/bin/bash
cd "$(dirname "$0")"
echo "Starting Financial Dashboard..."
open http://localhost:8765/dashboard.html &
sleep 1
python3 serve.py
