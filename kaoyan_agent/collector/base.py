# kaoyan_agent/collector/base.py
import sqlite3
import httpx
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CollectResult:
    success: bool
    schools_added: int = 0
    majors_added: int = 0
    scores_added: int = 0
    errors: list[str] = field(default_factory=list)


class WebCollector:
    def __init__(self, conn: sqlite3.Connection, timeout: int = 30):
        self.conn = conn
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            },
            follow_redirects=True,
        )

    def fetch(self, url: str) -> str:
        response = self.client.get(url)
        response.raise_for_status()
        return response.text

    def close(self):
        self.client.close()
