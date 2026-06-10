#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Seed dataset if empty
if [ ! -f data/live_jobs.json ]; then
    echo "Seeding initial dataset..."
    venv/bin/python scraper.py -f json -o data/live_jobs
fi

# Generate API keys if needed
if [ ! -f data/api_keys.json ]; then
    echo "Generating API keys..."
    venv/bin/python seed.py
fi

# Start API server
echo "Starting API server on port ${PORT:-8080}..."
exec venv/bin/python app.py
