#!/usr/bin/env python3
"""Initial setup: create API keys and seed dataset."""
import json
import os
import secrets

from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Generate initial API keys
keys_file = DATA_DIR / "api_keys.json"
if not keys_file.exists():
    admin_key = secrets.token_urlsafe(32)
    keys = {
        admin_key: {"plan": "admin", "rate_limit": 10000},
    }
    with open(keys_file, "w") as f:
        json.dump(keys, f, indent=2)
    print(f"Admin API key: {admin_key}")
    print(f"Saved to {keys_file}")
else:
    print(f"API keys already exist at {keys_file}")
    with open(keys_file) as f:
        keys = json.load(f)
    for k, v in keys.items():
        print(f"  Key: {k[:12]}... ({v['plan']})")
