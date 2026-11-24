from scraper.fetching.http_client import get_json
from scraper.fetching.job_scope import matches_target_scope

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"
ASHBY_BOARD_SLUGS = ["enter-ai", "tako", "skydropx", "whippy"]


def search_ashby_jobs(slug: str, max_retries: int = 3) -> dict[str, list[dict]]:
    response = get_json(
        f"{BASE_URL}/{slug}",
        params={"includeCompensation": True},
        max_retries=max_retries,
    )
    jobs = response.get("jobs", [])
    if not isinstance(jobs, list):
        raise ValueError(f"Unexpected Ashby jobs response for board '{slug}'.")

    filtered_jobs = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        description = " ".join(
            str(job.get(field) or "")
            for field in ("descriptionPlain", "descriptionHtml", "description")
        )
        location = job.get("location")
        if not location and job.get("isRemote"):
            location = "Remote"
        if matches_target_scope(location, description):
            filtered_jobs.append({**job, "_board_slug": slug})

    return {"jobs": filtered_jobs}
