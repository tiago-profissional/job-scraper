import os

import httpx

from scraper.fetching.http_client import get_json

BASE_URL = "https://serpapi.com/search.json"


def search_google_jobs(
    query: str,
    location: str = "Brazil",
    max_retries: int = 3,
) -> dict[str, list[dict]]:
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise ValueError("SERPAPI_API_KEY is not set.")

    try:
        response = get_json(
            BASE_URL,
            params={
                "api_key": api_key,
                "engine": "google_jobs",
                "q": query,
                "location": location,
                "gl": "br",
                "hl": "pt",
            },
            max_retries=max_retries,
        )
    except httpx.HTTPStatusError as err:
        raise RuntimeError(
            f"SerpApi returned HTTP {err.response.status_code}."
        ) from None
    except httpx.RequestError:
        raise RuntimeError("SerpApi request failed due to a network error.") from None

    if "error" in response:
        raise RuntimeError("SerpApi returned an API error.")
    jobs = response.get("jobs_results", [])
    if not isinstance(jobs, list):
        raise ValueError("Unexpected SerpApi response: 'jobs_results' must be an array.")
    return {"jobs": [job for job in jobs if isinstance(job, dict)]}
