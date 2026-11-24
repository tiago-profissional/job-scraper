import os
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import httpx

from scraper.fetching.job_scope import matches_target_scope
from scraper.fetching.jooble_client import search_jooble_jobs
from scraper.models.job import RawJob
from scraper.sources.base import JobSourceAdapter

JOOBLE_KEYWORDS = [
    "Estágio TI",
    "Suporte Técnico Júnior",
    "Desenvolvedor Júnior",
]
JOOBLE_LOCATIONS = ["Brasil", "Ceará", "Remoto"]


class JoobleAdapter(JobSourceAdapter):
    source_slug = "jooble"

    def discover(self) -> list[dict]:
        if not os.getenv("JOOBLE_API_KEY"):
            print("Jooble skipped: JOOBLE_API_KEY is not set.")
            return []

        all_jobs = []
        seen_ids: set[str] = set()
        for keyword in JOOBLE_KEYWORDS:
            for location in JOOBLE_LOCATIONS:
                try:
                    jobs = search_jooble_jobs(keyword, location).get("jobs", [])
                except (httpx.HTTPError, RuntimeError, ValueError) as err:
                    print(f"Error fetching Jooble jobs for '{keyword}' in '{location}': {err}")
                    continue

                for item in jobs:
                    description = item.get("summary") or item.get("snippet") or ""
                    if not matches_target_scope(item.get("location"), description):
                        continue
                    external_id = self.source_external_id(item)
                    if external_id and external_id in seen_ids:
                        continue
                    if external_id:
                        seen_ids.add(external_id)
                    all_jobs.append(item)
        return all_jobs

    def fetch(self, item: dict) -> dict:
        return item

    def parse(self, item: dict) -> RawJob:
        url = item.get("link", "")
        description = item.get("summary") or item.get("snippet") or ""
        return RawJob(
            source=self.source_slug,
            source_url=url,
            apply_url=url or None,
            external_id=self.source_external_id(item),
            title=item.get("title", ""),
            company=item.get("company", ""),
            description=description,
            location=item.get("location", ""),
            location_area=[],
            employment_type=item.get("type"),
            published_at=item.get("updated"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def canonicalize_url(self, url: str) -> str:
        parts = urlsplit(str(url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    def source_external_id(self, raw_job: dict) -> str | None:
        job_id = raw_job.get("id")
        return str(job_id) if job_id is not None else None
