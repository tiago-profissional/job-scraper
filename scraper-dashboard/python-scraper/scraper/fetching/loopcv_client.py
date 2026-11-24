import os

from scraper.fetching.http_client import get_json_list

BASE_URL = "https://b2b-api.loopcv.com/connect/loop"


def search_loopcv_jobs(
    loop_id: str | None = None,
    max_retries: int = 3,
) -> list[dict]:
    api_key = os.getenv("LOOPCV_API_KEY")
    if not api_key:
        raise ValueError("LOOPCV_API_KEY is not set.")

    configured_loop_id = loop_id or os.getenv("LOOPCV_LOOP_ID")
    if not configured_loop_id:
        raise ValueError("LOOPCV_LOOP_ID is not set.")

    response = get_json_list(
        f"{BASE_URL}/{configured_loop_id}/jobs",
        headers={"X-API-KEY": api_key},
        max_retries=max_retries,
    )
    return [job for job in response if isinstance(job, dict)]
