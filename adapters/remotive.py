import requests
from typing import Generator

from adapters.base import BaseAdapter
from models import JobListing
from utils.network import Rotator


class RemotiveAdapter(BaseAdapter):
    name = "remotive"

    def __init__(self, rotator: Rotator):
        self.http = rotator

    def scrape(self, query: str = "", **kwargs) -> Generator[JobListing, None, None]:
        url = "https://remotive.com/api/remote-jobs"
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("jobs", [])

        for item in jobs:
            title = item.get("title", "")
            if query and query.lower() not in title.lower():
                continue

            yield JobListing(
                title=title,
                company=item.get("company_name", ""),
                location=item.get("candidate_required_location", "") or "Remote",
                description=item.get("description", ""),
                url=item.get("url", ""),
                source="remotive",
                salary=item.get("salary", None),
                job_type=item.get("job_type", None),
                posted_date=item.get("publication_date", None),
            )
