import csv
import json
from pathlib import Path
from typing import Iterable

from models import JobListing


def to_csv(jobs: Iterable[JobListing], path: str):
    items = list(jobs)
    if not items:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=items[0].to_dict().keys())
        writer.writeheader()
        writer.writerows(j.to_dict() for j in items)
    print(f"Wrote {len(items)} jobs to {path}")


def to_json(jobs: Iterable[JobListing], path: str):
    items = list(jobs)
    if not items:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump([j.to_dict() for j in items], f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(items)} jobs to {path}")
