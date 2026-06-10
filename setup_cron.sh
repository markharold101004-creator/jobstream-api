#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
SCRAPER="$DIR/venv/bin/python $DIR/scheduler.py"

# Run daily at 6am UTC
(crontab -l 2>/dev/null; echo "0 6 * * * $SCRAPER >> $DIR/data/scrape.log 2>&1") | crontab -

echo "Cron installed. Scrapes daily at 6am UTC."
