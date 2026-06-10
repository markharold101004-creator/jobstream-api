from typing import Any, Dict, Iterable, List, Union

from models import JobListing


def _get_key(item: Union[JobListing, Dict[str, Any]]) -> tuple:
    if isinstance(item, dict):
        return (item.get("title", "").lower().strip(), item.get("company", "").lower().strip())
    return (item.title.lower().strip(), item.company.lower().strip())


def dedup(jobs: Iterable) -> list:
    seen = set()
    result = []
    for j in jobs:
        key = _get_key(j)
        if key not in seen:
            seen.add(key)
            result.append(j)
    return result


def merge_datasets(existing: list, new: Iterable) -> list:
    combined = list(existing) + list(new)
    return dedup(combined)
