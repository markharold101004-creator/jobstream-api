from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class JobListing:
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    url: str = ""
    source: str = ""
    salary: Optional[str] = None
    job_type: Optional[str] = None
    posted_date: Optional[str] = None
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return asdict(self)
