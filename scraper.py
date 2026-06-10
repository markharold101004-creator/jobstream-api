#!/usr/bin/env python3
import argparse
import sys

from adapters.remoteok import RemoteOKAdapter
from adapters.weworkremotely import WeWorkRemotelyAdapter
from adapters.remotive import RemotiveAdapter
from adapters.themuse import TheMuseAdapter
from adapters.himalayas import HimalayasAdapter
from export.formats import to_csv, to_json
from utils.network import Rotator

ADAPTERS = {
    "remoteok": RemoteOKAdapter,
    "weworkremotely": WeWorkRemotelyAdapter,
    "remotive": RemotiveAdapter,
    "themuse": TheMuseAdapter,
    "himalayas": HimalayasAdapter,
}


def main():
    parser = argparse.ArgumentParser(description="Job listings scraper")
    parser.add_argument(
        "--sources", "-s", nargs="+", choices=list(ADAPTERS),
        default=list(ADAPTERS), help="Job boards to scrape"
    )
    parser.add_argument("--query", "-q", default="", help="Keyword filter")
    parser.add_argument(
        "--format", "-f", choices=["csv", "json"], default="csv",
        help="Output format"
    )
    parser.add_argument("--output", "-o", default="data/jobs", help="Output path (without extension)")
    args = parser.parse_args()

    rotator = Rotator()
    all_jobs = []

    for name in args.sources:
        print(f"Scraping {name}...")
        adapter_cls = ADAPTERS[name]
        adapter = adapter_cls(rotator)
        jobs = list(adapter.scrape(args.query))
        all_jobs.extend(jobs)
        print(f"  Found {len(jobs)} jobs from {name}")

    if not all_jobs:
        print("No jobs found.")
        sys.exit(0)

    ext = args.format
    out_path = f"{args.output}.{ext}"
    if ext == "csv":
        to_csv(all_jobs, out_path)
    else:
        to_json(all_jobs, out_path)


if __name__ == "__main__":
    main()
