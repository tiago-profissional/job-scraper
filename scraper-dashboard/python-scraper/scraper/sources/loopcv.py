from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import httpx

from scraper.fetching.job_scope import matches_target_scope
from scraper.fetching.loopcv_client import search_loopcv_jobs
from scraper.models.job import RawJob
from scraper.sources.base import JobSourceAdapter


class LoopCVAdapter(JobSourceAdapter):
    source_slug = "loopcv"

    def discover(self) -> list[dict]:
        try:
            jobs = search_loopcv_jobs()
        except (httpx.HTTPError, RuntimeError, ValueError) as err:
            print(f"Error fetching LoopCV jobs: {err}")
            return []
        return [
            item
            for item in jobs
            if matches_target_scope(item.get("location"), item.get("summary"))
        ]

    def fetch(self, item: dict) -> dict:
        return item

    def parse(self, item: dict) -> RawJob:
        url = item.get("url", "")
        return RawJob(
            source=self.source_slug,
            source_url=url,
            apply_url=url or None,
            external_id=self.source_external_id(item),
            title=item.get("title", ""),
            company=item.get("company", ""),
            description=item.get("summary", ""),
            location=item.get("location", ""),
            location_area=[],
            employment_type=item.get("job_type"),
            published_at=item.get("createdAtDate"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def canonicalize_url(self, url: str) -> str:
        parts = urlsplit(str(url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    def source_external_id(self, raw_job: dict) -> str | None:
        job_id = raw_job.get("_id")
        return str(job_id) if job_id is not None else None
