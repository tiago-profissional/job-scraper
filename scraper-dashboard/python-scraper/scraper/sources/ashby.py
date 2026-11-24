from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from scraper.fetching.ashby_client import ASHBY_BOARD_SLUGS, search_ashby_jobs
from scraper.models.job import RawJob
from scraper.sources.base import JobSourceAdapter


class AshbyAdapter(JobSourceAdapter):
    source_slug = "ashby"

    def discover(self) -> list[dict]:
        all_jobs = []
        seen_ids: set[str] = set()
        for slug in ASHBY_BOARD_SLUGS:
            try:
                jobs = search_ashby_jobs(slug).get("jobs", [])
            except Exception as err:
                print(f"Error fetching Ashby board '{slug}': {err}")
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
        if not location and item.get("isRemote"):
            location = "Remote"

        board_slug = item.get("_board_slug", "")
        company = (
            item.get("organizationName")
            or item.get("companyName")
            or board_slug.replace("-", " ").title()
        )
        description = (
            item.get("descriptionPlain")
            or item.get("descriptionHtml")
            or item.get("description")
            or ""
        )
        return RawJob(
            source=self.source_slug,
            source_url=item.get("jobUrl") or item.get("applyUrl", ""),
            external_id=self.source_external_id(item),
            title=item.get("title", ""),
            company=company,
            description=description,
            location=location,
            location_area=[],
            employment_type=item.get("employmentType"),
            published_at=item.get("publishedAt"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def canonicalize_url(self, url: str) -> str:
        parts = urlsplit(str(url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    def source_external_id(self, raw_job: dict) -> str | None:
        job_id = raw_job.get("id") or raw_job.get("jobId")
        board_slug = raw_job.get("_board_slug", "")
        return f"{board_slug}:{job_id}" if job_id is not None else None
