from scraper.fetching.http_client import get_json
from scraper.fetching.job_scope import matches_target_scope

BASE_URL = "https://api.greenhouse.io/v1/boards"
GREENHOUSE_BOARD_SLUGS = [
    "quintoandar",
    "inter",
    "xpinc",
    "gympass",
    "stonepatrocina",
    "arcoeducacao",
    "elo",
    "wizinc",
    "platformscience",
]


def search_greenhouse_jobs(slug: str, max_retries: int = 3) -> dict[str, list[dict]]:
    response = get_json(
        f"{BASE_URL}/{slug}/jobs",
        params={"content": True},
        max_retries=max_retries,
    )
    jobs = response.get("jobs", [])
    if not isinstance(jobs, list):
        raise ValueError(f"Unexpected Greenhouse jobs response for board '{slug}'.")

    filtered_jobs = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        location = job.get("location")
        description = job.get("content", "")
        if matches_target_scope(location, description):
            filtered_jobs.append({**job, "_board_slug": slug})

    return {"jobs": filtered_jobs}
