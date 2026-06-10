import requests
from typing import Generator

from adapters.base import BaseAdapter
from models import JobListing
from utils.network import Rotator


class TheMuseAdapter(BaseAdapter):
    name = "themuse"

    def __init__(self, rotator: Rotator):
        self.http = rotator

    def scrape(self, query: str = "", **kwargs) -> Generator[JobListing, None, None]:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        page = 0
        total_pages = 3

        while page < total_pages:
            url = f"https://www.themuse.com/api/public/jobs?page={page}"
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])

            if not results:
                break

            for item in results:
                title = item.get("name", "")
                if query and query.lower() not in title.lower():
                    continue

                company = ""
                if item.get("company"):
                    company = item["company"].get("name", "")

                locations = item.get("locations", [])
                location = ", ".join(l.get("name", "") for l in locations) if locations else None

                publication_date = None
                if item.get("publication_date"):
                    publication_date = item["publication_date"]

                yield JobListing(
                    title=title,
                    company=company,
                    location=location,
                    url=item.get("refs", {}).get("landing_page", ""),
                    source="themuse",
                    job_type=item.get("type", None),
                    posted_date=publication_date,
                )

            page += 1
