#!/bin/bash
# NDK Pack List Org – Mac launcher (double-click this file)

cd "$(dirname "$0")"

# Create venv if needed
if [ ! -d "venv" ]; then
  echo "Setting up NDK Pack List Org the first time..."
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
else
  source venv/bin/activate
fi

# Open the browser after a short delay
(sleep 2 && open "http://127.0.0.1:5000") &

echo "Starting NDK Pack List Org..."
echo "Keep this window open while packing."
echo "On iPads open: http://$(ipconfig getifaddr en0 2>/dev/null || hostname):5000"
echo ""
python app.py
