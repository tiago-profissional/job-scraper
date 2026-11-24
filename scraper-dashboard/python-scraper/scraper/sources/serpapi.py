from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import httpx

from scraper.fetching.job_scope import matches_target_scope
from scraper.fetching.serpapi_client import search_google_jobs
from scraper.models.job import RawJob
from scraper.sources.base import JobSourceAdapter

SERPAPI_QUERIES = [
    "Estágio TI",
    "Suporte Técnico Júnior",
    "Desenvolvedor Júnior",
]


class SerpApiAdapter(JobSourceAdapter):
    source_slug = "serpapi"

    def discover(self) -> list[dict]:
        all_jobs = []
        seen_ids: set[str] = set()
        for query in SERPAPI_QUERIES:
            try:
                jobs = search_google_jobs(query).get("jobs", [])
            except (httpx.HTTPError, RuntimeError, ValueError) as err:
                print(f"Error fetching SerpApi jobs for '{query}': {err}")
                continue

            for item in jobs:
                if not matches_target_scope(item.get("location"), item.get("description")):
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
        apply_options = item.get("apply_options") or []
        detected_extensions = item.get("detected_extensions")
        if not isinstance(detected_extensions, dict):
            detected_extensions = {}
        apply_url = next(
            (
                option.get("link")
                for option in apply_options
                if isinstance(option, dict) and option.get("link")
            ),
            None,
        )
        return RawJob(
            source=self.source_slug,
            source_url=item.get("share_link") or apply_url or "",
            apply_url=apply_url,
            external_id=self.source_external_id(item),
            title=item.get("title", ""),
            company=item.get("company_name", ""),
            description=item.get("description", ""),
            location=item.get("location", ""),
            location_area=[],
            employment_type=detected_extensions.get("schedule_type"),
            published_at=detected_extensions.get("posted_at"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def canonicalize_url(self, url: str) -> str:
        parts = urlsplit(str(url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    def source_external_id(self, raw_job: dict) -> str | None:
        job_id = raw_job.get("job_id")
        return str(job_id) if job_id is not None else None
