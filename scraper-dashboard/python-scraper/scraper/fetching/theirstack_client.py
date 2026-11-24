import os

import httpx

from scraper.fetching.http_client import post_json

BASE_URL = "https://api.theirstack.com/v1/jobs/search"
DEFAULT_JOB_TITLES = [
    "estágio ti",
    "suporte técnico",
    "help desk",
    "helpdesk",
    "infraestrutura",
    "desenvolvedor júnior",
    "junior developer",
]


def search_theirstack_jobs(
    limit: int = 5,
    page: int = 0,
    max_retries: int = 3,
) -> dict[str, list[dict]]:
    api_key = os.getenv("THEIRSTACK_API_KEY")
    if not api_key:
        raise ValueError("THEIRSTACK_API_KEY is not set.")
    if limit < 1:
        raise ValueError("limit must be at least 1.")

    try:
        response = post_json(
            BASE_URL,
            {
                "job_title_or": DEFAULT_JOB_TITLES,
                "job_country_code_or": ["BR"],
                "posted_at_max_age_days": 30,
                "limit": limit,
                "page": page,
                "include_total_results": False,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            max_retries=max_retries,
        )
    except httpx.HTTPStatusError as err:
        raise RuntimeError(
            f"TheirStack API returned HTTP {err.response.status_code}."
        ) from None
    except httpx.RequestError:
        raise RuntimeError("TheirStack API request failed due to a network error.") from None

    jobs = response.get("data")
    if not isinstance(jobs, list):
        raise ValueError("Unexpected TheirStack response: 'data' must be an array.")
    return {"jobs": [job for job in jobs if isinstance(job, dict)]}
