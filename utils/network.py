import random
import time
from typing import Optional

from fake_useragent import UserAgent


class Rotator:
    def __init__(self):
        self.ua = UserAgent(browsers=["chrome", "firefox", "edge"])
        self._proxies: list[str] = []
        self._proxy_index = 0

    def load_proxies(self, filepath: str):
        with open(filepath) as f:
            self._proxies = [line.strip() for line in f if line.strip()]

    def random_headers(self) -> dict:
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def next_proxy(self) -> Optional[dict]:
        if not self._proxies:
            return None
        proxy = self._proxies[self._proxy_index % len(self._proxies)]
        self._proxy_index += 1
        return {"http": proxy, "https": proxy}

    def wait(self, min_s: float = 1.0, max_s: float = 3.0):
        time.sleep(random.uniform(min_s, max_s))
