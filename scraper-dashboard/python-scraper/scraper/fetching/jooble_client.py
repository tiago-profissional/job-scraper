import os

import httpx

from scraper.fetching.http_client import post_json

BASE_URL = "https://jooble.org/api"


def search_jooble_jobs(
    keywords: str,
    location: str,
    max_retries: int = 3,
) -> dict[str, list[dict]]:
    api_key = os.getenv("JOOBLE_API_KEY")
    if not api_key:
        raise ValueError("JOOBLE_API_KEY is not set.")

    try:
        response = post_json(
            f"{BASE_URL}/{api_key}",
            {"keywords": keywords, "location": location},
            max_retries=max_retries,
        )
    except httpx.HTTPStatusError as err:
        raise RuntimeError(
            f"Jooble API returned HTTP {err.response.status_code}."
        ) from None
    except httpx.RequestError:
        raise RuntimeError("Jooble API request failed due to a network error.") from None

    jobs = response.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("Unexpected Jooble response: 'jobs' must be an array.")
    return {"jobs": [job for job in jobs if isinstance(job, dict)]}
