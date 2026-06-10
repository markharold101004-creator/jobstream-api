import requests
from typing import Generator

from adapters.base import BaseAdapter
from models import JobListing
from utils.network import Rotator


class JobsbaseAdapter(BaseAdapter):
    name = "jobsbase"

    def __init__(self, rotator: Rotator):
        self.http = rotator

    def scrape(self, query: str = "", **kwargs) -> Generator[JobListing, None, None]:
        url = "https://jobsbase.io/api/v1/jobs?limit=100"
        if query:
            url += f"&q={query}"

        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        jobs = data if isinstance(data, list) else data.get("data", data.get("jobs", []))

        for item in jobs:
            title = item.get("title", "")
            if query and query.lower() not in title.lower():
                continue

            location = None
            locs = item.get("locations", [])
            if locs:
                location = ", ".join((l.get("city") or l.get("name") or "") for l in locs if l)

            salary = None
            if item.get("salary_min") or item.get("salary_max"):
                salary = f'{item.get("salary_min", "")} - {item.get("salary_max", "")}'.strip(" -")

            yield JobListing(
                title=title,
                company=item.get("company", {}).get("name", "") if isinstance(item.get("company"), dict) else "",
                location=location or item.get("workplace", "Remote"),
                url=item.get("url", item.get("apply_url", "")),
                source="jobsbase",
                salary=salary,
                job_type=item.get("type", None),
                posted_date=item.get("posted_at", None),
            )
