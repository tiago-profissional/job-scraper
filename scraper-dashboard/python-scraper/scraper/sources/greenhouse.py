from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from scraper.fetching.greenhouse_client import (
    GREENHOUSE_BOARD_SLUGS,
    search_greenhouse_jobs,
)
from scraper.models.job import RawJob
from scraper.sources.base import JobSourceAdapter


class GreenhouseAdapter(JobSourceAdapter):
    source_slug = "greenhouse"

    def discover(self) -> list[dict]:
        all_jobs = []
        seen_ids: set[str] = set()
        for slug in GREENHOUSE_BOARD_SLUGS:
            try:
                jobs = search_greenhouse_jobs(slug).get("jobs", [])
            except Exception as err:
                print(f"Error fetching Greenhouse board '{slug}': {err}")
                continue

            for item in jobs:
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
        location_value = item.get("location")
        if isinstance(location_value, dict):
            location = location_value.get("name", "")
        else:
            location = str(location_value or "")
        board_slug = item.get("_board_slug", "")
        company = item.get("company_name") or board_slug.replace("-", " ").title()
        return RawJob(
            source=self.source_slug,
            source_url=item.get("absolute_url", ""),
            external_id=self.source_external_id(item),
            title=item.get("title", ""),
            company=company,
            description=item.get("content", ""),
            location=location,
            location_area=[],
            published_at=item.get("updated_at"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def canonicalize_url(self, url: str) -> str:
        parts = urlsplit(str(url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    def source_external_id(self, raw_job: dict) -> str | None:
        job_id = raw_job.get("id")
        board_slug = raw_job.get("_board_slug", "")
        return f"{board_slug}:{job_id}" if job_id is not None else None
