#!/usr/bin/env python3
"""Run scheduled scrapes and maintain a live dataset."""
import json
import os
import sys
from datetime import datetime, timezone

from export.dedup import merge_datasets
from export.formats import to_csv, to_json
from scraper import ADAPTERS
from utils.network import Rotator

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LIVE_FILE = os.path.join(DATA_DIR, "live_jobs.json")


def load_live() -> list:
    if os.path.exists(LIVE_FILE):
        with open(LIVE_FILE) as f:
            return json.load(f)
    return []


def save_live(jobs: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    to_json(jobs, LIVE_FILE)


def run_scrape_all(out_dir: str = DATA_DIR):
    os.makedirs(out_dir, exist_ok=True)

    rotator = Rotator()
    existing = load_live()
    all_new = []

    for name, adapter_cls in ADAPTERS.items():
        print(f"[{datetime.now(timezone.utc).isoformat()}] Scraping {name}...")
        try:
            adapter = adapter_cls(rotator)
            jobs = list(adapter.scrape(""))
            print(f"  Got {len(jobs)} jobs")
            all_new.extend(jobs)
        except Exception as e:
            print(f"  ERROR: {e}")

    merged = merge_datasets(existing, all_new)
    save_live(merged)

    # also dump timestamped snapshot
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_path = os.path.join(out_dir, f"jobs_{ts}")
    to_json(merged, f"{snapshot_path}.json")
    to_csv(merged, f"{snapshot_path}.csv")

    print(f"Live dataset: {len(merged)} jobs total")


if __name__ == "__main__":
    run_scrape_all()
