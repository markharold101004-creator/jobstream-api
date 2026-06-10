import requests
from typing import Generator

from adapters.base import BaseAdapter
from models import JobListing
from utils.network import Rotator


class HimalayasAdapter(BaseAdapter):
    name = "himalayas"

    def __init__(self, rotator: Rotator):
        self.http = rotator

    def scrape(self, query: str = "", **kwargs) -> Generator[JobListing, None, None]:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        limit = kwargs.get("limit", 50)
        url = f"https://himalayas.app/jobs/api?limit={limit}"

        if query:
            url += f"&query={query}"

        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("jobs", [])

        for item in jobs:
            title = item.get("title", "")
            if query and query.lower() not in title.lower():
                continue

            salary = None
            if item.get("minSalary") or item.get("maxSalary"):
                salary = f'{item.get("minSalary", "")} - {item.get("maxSalary", "")}'.strip(" -")

            yield JobListing(
                title=title,
                company=item.get("companyName", ""),
                location=item.get("location", "") or "Remote",
                description=item.get("excerpt", ""),
                url=f"https://himalayas.app/jobs/{item.get('companySlug', '')}/{item.get('slug', '')}" if item.get('slug') else "",
                source="himalayas",
                salary=salary,
                job_type=item.get("employmentType", None),
            )
