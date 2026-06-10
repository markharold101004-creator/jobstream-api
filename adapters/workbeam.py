import requests
from typing import Generator

from adapters.base import BaseAdapter
from models import JobListing
from utils.network import Rotator


class WorkbeamAdapter(BaseAdapter):
    name = "workbeam"

    def __init__(self, rotator: Rotator):
        self.http = rotator

    def scrape(self, query: str = "", **kwargs) -> Generator[JobListing, None, None]:
        url = "https://workbeamhq.com/api/v1/jobs?limit=50"
        if query:
            url += f"&q={query}"

        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("jobs", [])

        for item in jobs:
            title = item.get("title", "")
            if query and query.lower() not in title.lower():
                continue

            salary = None
            if item.get("salaryMin") or item.get("salaryMax"):
                salary = f'{item.get("salaryMin", "")} - {item.get("salaryMax", "")}'.strip(" -")

            yield JobListing(
                title=title,
                company=item.get("company", ""),
                location=item.get("location", "Remote"),
                description=item.get("description", ""),
                url=item.get("url", item.get("applyUrl", "")),
                source="workbeam",
                salary=salary,
                posted_date=item.get("postedAt", None),
            )
