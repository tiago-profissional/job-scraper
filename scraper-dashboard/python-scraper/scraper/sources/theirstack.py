from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import httpx

from scraper.fetching.job_scope import matches_target_scope
from scraper.fetching.theirstack_client import search_theirstack_jobs
from scraper.models.job import RawJob
from scraper.sources.base import JobSourceAdapter


class TheirStackAdapter(JobSourceAdapter):
    source_slug = "theirstack"

    def discover(self) -> list[dict]:
        try:
            jobs = search_theirstack_jobs().get("jobs", [])
        except (httpx.HTTPError, RuntimeError, ValueError) as err:
            print(f"Error fetching TheirStack jobs: {err}")
            return []
        return [
            item
            for item in jobs
            if matches_target_scope(
                item.get("location"),
                item.get("description") or item.get("job_description"),
            )
        ]

    def fetch(self, item: dict) -> dict:
        return item

    def parse(self, item: dict) -> RawJob:
        company_object = item.get("company_object")
        company = item.get("company") or (
            company_object.get("name", "") if isinstance(company_object, dict) else ""
        )
        url = item.get("url") or item.get("final_url") or ""
        employment_statuses = item.get("employment_statuses")
        employment_type = (
            employment_statuses[0]
            if isinstance(employment_statuses, list) and employment_statuses
            else None
        )
        return RawJob(
            source=self.source_slug,
            source_url=url,
            apply_url=item.get("final_url") or url or None,
            external_id=self.source_external_id(item),
            title=item.get("job_title") or item.get("title", ""),
            company=company,
            description=item.get("description") or item.get("job_description") or "",
            location=item.get("location") or item.get("job_location", ""),
            location_area=[],
            employment_type=employment_type,
            published_at=item.get("date_posted") or item.get("posted_at"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def canonicalize_url(self, url: str) -> str:
        parts = urlsplit(str(url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    def source_external_id(self, raw_job: dict) -> str | None:
        job_id = raw_job.get("id")
        return str(job_id) if job_id is not None else None
