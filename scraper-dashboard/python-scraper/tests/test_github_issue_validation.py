from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest

from scraper.fetching.http_client import (
    check_github_issue_job_posting,
    check_url_alive,
    is_github_issue_job_posting,
    is_github_issue_open,
)
from scraper.models.job import NormalizedJob, WorkMode
from scraper.validation.job_validator import validate_job

ISSUE_URL = "https://github.com/acme/jobs/issues/201"
JOB_TITLE = "We're hiring: Backend Engineer"
JOB_BODY = (
    "Responsibilities include building APIs and maintaining our services. "
    "Requirements include Python experience and knowledge of databases. "
    "Location: Remote. How to apply: send your application to "
    "https://careers.example.com/backend."
)


def api_response(issue: dict, status_code: int = 200) -> Mock:
    response = Mock(status_code=status_code)
    response.json.return_value = issue
    return response


def make_job(**changes) -> NormalizedJob:
    job = {
        "source": "arbeitnow",
        "source_url": ISSUE_URL,
        "title": "Backend Engineer",
        "company": "Acme",
        "description": JOB_BODY,
        "location": "Remote",
        "work_mode": WorkMode.REMOTE,
        "published_at": None,
        "apply_url": None,
    }
    job.update(changes)
    return NormalizedJob.model_construct(**job)


def test_invalid_github_issue_url_is_not_open():
    with patch("scraper.fetching.http_client.httpx.get") as get:
        assert not is_github_issue_open("https://github.com/org/repo/issues/not-an-id")

    get.assert_not_called()


def test_github_issue_must_be_open():
    response = api_response({"state": "closed"})

    with patch("scraper.fetching.http_client.httpx.get", return_value=response):
        assert not is_github_issue_open(ISSUE_URL)


def test_github_issue_404_is_not_open():
    response = api_response({}, status_code=404)

    with patch("scraper.fetching.http_client.httpx.get", return_value=response):
        assert not is_github_issue_open(ISSUE_URL)
        assert check_github_issue_job_posting(ISSUE_URL) == (
            False,
            "github_issue_not_valid_job",
        )


def test_github_api_failure_is_not_confirmed_as_invalid():
    response = api_response({}, status_code=503)

    with patch("scraper.fetching.http_client.httpx.get", return_value=response):
        assert check_github_issue_job_posting(ISSUE_URL) == (
            False,
            "github_issue_check_failed",
        )


def test_github_timeout_is_not_confirmed_as_invalid():
    with patch(
        "scraper.fetching.http_client.httpx.get",
        side_effect=httpx.TimeoutException("request timed out"),
    ):
        assert check_github_issue_job_posting(ISSUE_URL) == (
            False,
            "github_issue_check_failed",
        )


def test_open_github_issue_is_valid():
    response = api_response({"state": "open"})

    with patch("scraper.fetching.http_client.httpx.get", return_value=response):
        assert is_github_issue_open(ISSUE_URL)


def test_github_pull_request_is_rejected():
    response = api_response({
        "state": "open",
        "title": JOB_TITLE,
        "body": JOB_BODY,
        "pull_request": {"url": "https://api.github.com/repos/acme/jobs/pulls/201"},
    })

    with patch("scraper.fetching.http_client.httpx.get", return_value=response):
        assert not is_github_issue_open(ISSUE_URL)
        assert not is_github_issue_job_posting(ISSUE_URL)


def test_generic_open_issue_is_not_a_job_posting():
    response = api_response({
        "state": "open",
        "title": "Discussion about repository requirements",
        "body": (
            "This thread discusses project requirements and how to apply a patch. "
            * 5
        ),
    })

    with patch("scraper.fetching.http_client.httpx.get", return_value=response):
        assert not is_github_issue_job_posting(ISSUE_URL)


def test_discussion_about_a_job_is_not_a_job_posting():
    response = api_response({
        "state": "open",
        "title": "Discussion: how do I apply for a job opening?",
        "body": (
            "Can someone explain the requirements and how to apply for a job? "
            "This is a question, not a hiring announcement."
        ),
    })

    with patch("scraper.fetching.http_client.httpx.get", return_value=response):
        assert not is_github_issue_job_posting(ISSUE_URL)


def test_open_github_job_issue_passes_full_validation():
    response = api_response({
        "state": "open",
        "title": JOB_TITLE,
        "body": JOB_BODY,
    })

    with (
        patch("scraper.fetching.http_client.httpx.get", return_value=response),
        patch(
            "scraper.validation.job_validator.check_url_alive",
            return_value=(True, ""),
        ),
    ):
        assert validate_job(make_job()) == []


def test_arbitrary_domain_is_not_allowed_for_arbeitnow():
    job = make_job(source_url="https://example.com/jobs/backend")

    assert "domain_not_allowed" in validate_job(job)


@pytest.mark.parametrize("text", ["requirements", "apply", "requirements apply"])
def test_generic_html_with_isolated_job_words_is_rejected(text):
    html = (
        "<html><head><title>Account settings</title></head><body>"
        + (f"General information about this page: {text}. " * 12)
        + "</body></html>"
    )
    response = SimpleNamespace(
        status_code=200,
        url="https://example.com/account",
        text=html,
        headers={"Content-Type": "text/html"},
    )

    with patch("scraper.fetching.http_client.httpx.get", return_value=response):
        assert check_url_alive("https://example.com/account") == (
            False,
            "soft_404_no_job_signals",
        )


def test_html_with_combined_job_signals_is_accepted():
    html = (
        "<html><head><title>We're hiring</title></head><body>"
        + (
            "We're hiring a backend engineer. Responsibilities include building APIs. "
            "Requirements include Python experience. "
            * 5
        )
        + "</body></html>"
    )
    response = SimpleNamespace(
        status_code=200,
        url="https://example.com/jobs/backend",
        text=html,
        headers={"Content-Type": "text/html"},
    )

    with patch("scraper.fetching.http_client.httpx.get", return_value=response):
        assert check_url_alive("https://example.com/jobs/backend") == (True, "")


def test_html_with_job_posting_schema_is_accepted():
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"JobPosting"}'
        "</script></head><body>Backend Engineer</body></html>"
    )
    response = SimpleNamespace(
        status_code=200,
        url="https://example.com/jobs/backend",
        text=html,
        headers={"Content-Type": "text/html"},
    )

    with patch("scraper.fetching.http_client.httpx.get", return_value=response):
        assert check_url_alive("https://example.com/jobs/backend") == (True, "")
