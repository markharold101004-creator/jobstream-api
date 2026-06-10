import requests
from typing import Generator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from adapters.base import BaseAdapter
from models import JobListing
from utils.network import Rotator


BASE = "https://weworkremotely.com"


class WeWorkRemotelyAdapter(BaseAdapter):
    name = "weworkremotely"

    def __init__(self, rotator: Rotator):
        self.http = rotator

    def scrape(self, query: str = "", **kwargs) -> Generator[JobListing, None, None]:
        url = urljoin(BASE, "/remote-jobs")
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for li in soup.select("section.jobs ul li"):
            link = li.select_one("a.listing-link--unlocked")
            if not link:
                continue

            title_el = link.select_one(".new-listing__header__title__text, .new-listing__header__title")
            company_el = link.select_one(".new-listing__company-name")
            location_el = link.select_one(".new-listing__company-headquarters")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""

            if not title:
                continue
            if query and query.lower() not in title.lower():
                continue

            location = location_el.get_text(strip=True) if location_el else None

            yield JobListing(
                title=title,
                company=company,
                location=location or "Remote",
                url=urljoin(BASE, link.get("href", "")),
                source="weworkremotely",
                job_type="Remote",
            )
