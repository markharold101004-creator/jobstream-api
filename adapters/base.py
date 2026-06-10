from abc import ABC, abstractmethod
from typing import Generator

from models import JobListing


class BaseAdapter(ABC):
    name: str = ""

    @abstractmethod
    def scrape(self, query: str, **kwargs) -> Generator[JobListing, None, None]:
        ...

    def normalize(self, raw: dict) -> JobListing:
        return JobListing(**raw)
