import requests
from typing import Generator

from adapters.base import BaseAdapter
from models import JobListing
from utils.network import Rotator


class JobicyAdapter(BaseAdapter):
    name = "jobicy"

    def __init__(self, rotator: Rotator):
        self.http = rotator

    def scrape(self, query: str = "", **kwargs) -> Generator[JobListing, None, None]:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        count = kwargs.get("count", 50)
        url = f"https://jobicy.com/api/v2/remote-jobs?count={count}"
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("data", [])

        for item in jobs:
            title = item.get("jobTitle", "")
            if query and query.lower() not in title.lower():
                continue

            salary = None
            if item.get("salaryMin") or item.get("salaryMax"):
                salary = f'{item.get("salaryMin", "")} - {item.get("salaryMax", "")}'.strip(" -")
                if item.get("salaryCurrency"):
                    salary = f"{salary} {item['salaryCurrency']}"

            yield JobListing(
                title=title,
                company=item.get("companyName", ""),
                location=item.get("jobGeo", "") or "Remote",
                url=item.get("url", ""),
                source="jobicy",
                salary=salary,
                job_type=item.get("jobType", None),
                posted_date=item.get("pubDate", None),
            )
