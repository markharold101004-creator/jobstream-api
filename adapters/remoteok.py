import requests
from typing import Generator

from adapters.base import BaseAdapter
from models import JobListing
from utils.network import Rotator


class RemoteOKAdapter(BaseAdapter):
    name = "remoteok"

    def __init__(self, rotator: Rotator):
        self.http = rotator

    def scrape(self, query: str = "", **kwargs) -> Generator[JobListing, None, None]:
        url = "https://remoteok.com/api"
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        jobs = resp.json()
        if not isinstance(jobs, list):
            return

        for item in jobs:
            if not isinstance(item, dict) or "id" not in item:
                continue
            title = item.get("position", "")
            if query and query.lower() not in title.lower():
                continue

            salary = None
            if item.get("salary_min") or item.get("salary_max"):
                salary = f'{item.get("salary_min", "")} - {item.get("salary_max", "")}'.strip(" -")

            yield JobListing(
                title=title,
                company=item.get("company", ""),
                location=item.get("location", "Remote") or "Remote",
                description=item.get("description", ""),
                url=item.get("url", ""),
                source="remoteok",
                salary=salary,
                job_type="Remote",
                posted_date=item.get("date", None),
            )
