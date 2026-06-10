import csv
import json
from pathlib import Path
from typing import Iterable

from models import JobListing


def _normalize(j):
    return j.to_dict() if hasattr(j, "to_dict") else j

def to_csv(jobs: Iterable, path: str):
    items = [j if isinstance(j, dict) else j.to_dict() for j in jobs]
    if not items:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=items[0].keys())
        writer.writeheader()
        writer.writerows(items)
    print(f"Wrote {len(items)} jobs to {path}")


def to_json(jobs: Iterable, path: str):
    items = [_normalize(j) for j in jobs]
    if not items:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(items)} jobs to {path}")
