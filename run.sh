#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Creating a virtual environment the first time this runs..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "Checking dependencies..."
pip install -q -r requirements.txt

echo
echo "Starting TGH Shorts Studio..."
python desktop.py
