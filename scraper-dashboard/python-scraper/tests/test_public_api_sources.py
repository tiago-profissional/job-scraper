from scraper.fetching import ashby_client, greenhouse_client
from scraper.fetching.http_client import get_json
from scraper.models.job import RawJob
from scraper.normalization.job_normalizer import normalize_job
from scraper.sources.ashby import AshbyAdapter
from scraper.sources.greenhouse import GreenhouseAdapter
from scraper.validation import job_validator


def test_http_client_requests_json_with_query_parameters(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"jobs": []}

    def fake_get(url, *, params, timeout):
        calls.append((url, params, timeout))
        return FakeResponse()

    monkeypatch.setattr("scraper.fetching.http_client.httpx.get", fake_get)

    assert get_json(
        "https://api.greenhouse.io/v1/boards/example/jobs",
        params={"content": True},
    ) == {"jobs": []}
    assert calls == [
        (
            "https://api.greenhouse.io/v1/boards/example/jobs",
            {"content": True},
            10.0,
        )
    ]


def test_greenhouse_client_filters_jobs_by_location_or_description(monkeypatch):
    calls = []

    def fake_get_json(url, *, params, max_retries):
        calls.append((url, params, max_retries))
        return {
            "jobs": [
                {
                    "id": 1,
                    "title": "Engenheiro de Software",
                    "location": {"name": "Fortaleza, CE"},
                    "content": "<p>Trabalho híbrido</p>",
                },
                {
                    "id": 2,
                    "title": "Engineer",
                    "location": {"name": "New York"},
                    "content": "<p>Remote anywhere in Brazil</p>",
                },
                {
                    "id": 3,
                    "title": "Engineer",
                    "location": {"name": "London"},
                    "content": "<p>On-site in London</p>",
                },
            ]
        }

    monkeypatch.setattr(greenhouse_client, "get_json", fake_get_json)

    response = greenhouse_client.search_greenhouse_jobs("quintoandar", max_retries=2)

    assert [job["id"] for job in response["jobs"]] == [1, 2]
    assert all(job["_board_slug"] == "quintoandar" for job in response["jobs"])
    assert calls == [
        (
            "https://api.greenhouse.io/v1/boards/quintoandar/jobs",
            {"content": True},
            2,
        )
    ]


def test_ashby_client_filters_jobs_by_location_or_description(monkeypatch):
    calls = []

    def fake_get_json(url, *, params, max_retries):
        calls.append((url, params, max_retries))
        return {
            "jobs": [
                {
                    "id": "br-role",
                    "title": "Analista",
                    "location": "Recife, Brasil",
                    "descriptionPlain": "Modelo híbrido.",
                },
                {
                    "id": "remote-role",
                    "title": "Engineer",
                    "location": "United States",
                    "descriptionPlain": "Remote role open to Latam candidates.",
                },
                {
                    "id": "local-role",
                    "title": "Engineer",
                    "location": "Berlin",
                    "descriptionPlain": "On-site in Germany.",
                },
            ]
        }

    monkeypatch.setattr(ashby_client, "get_json", fake_get_json)

    response = ashby_client.search_ashby_jobs("enter-ai")

    assert [job["id"] for job in response["jobs"]] == ["br-role", "remote-role"]
    assert all(job["_board_slug"] == "enter-ai" for job in response["jobs"])
    assert calls == [
        (
            "https://api.ashbyhq.com/posting-api/job-board/enter-ai",
            {"includeCompensation": True},
            3,
        )
    ]


def test_adapters_map_board_jobs_to_raw_job_models(monkeypatch):
    greenhouse_job = {
        "id": 42,
        "_board_slug": "quintoandar",
        "title": "Backend Engineer",
        "absolute_url": "https://boards.greenhouse.io/quintoandar/jobs/42",
        "location": {"name": "Salvador, BA"},
        "content": "Descrição da vaga",
        "updated_at": "2026-11-20T10:00:00Z",
    }
    ashby_job = {
        "id": "abc",
        "_board_slug": "enter-ai",
        "title": "Backend Engineer",
        "jobUrl": "https://jobs.ashbyhq.com/enter-ai/abc",
        "location": "Remoto no Brasil",
        "descriptionPlain": "Descrição da vaga",
        "publishedAt": "2026-11-20T10:00:00Z",
    }
    monkeypatch.setattr(
        "scraper.sources.greenhouse.search_greenhouse_jobs",
        lambda slug: (
            {"jobs": [greenhouse_job]}
            if slug == greenhouse_job["_board_slug"]
            else {"jobs": []}
        ),
    )
    monkeypatch.setattr(
        "scraper.sources.ashby.search_ashby_jobs",
        lambda slug: (
            {"jobs": [ashby_job]}
            if slug == ashby_job["_board_slug"]
            else {"jobs": []}
        ),
    )

    greenhouse = GreenhouseAdapter()
    ashby = AshbyAdapter()
    greenhouse_raw = greenhouse.parse(greenhouse.fetch(greenhouse.discover()[0]))
    ashby_raw = ashby.parse(ashby.fetch(ashby.discover()[0]))

    assert greenhouse_raw.source == "greenhouse"
    assert greenhouse_raw.external_id == "quintoandar:42"
    assert greenhouse_raw.location == "Salvador, BA"
    assert str(greenhouse_raw.source_url) == greenhouse_job["absolute_url"]
    assert ashby_raw.source == "ashby"
    assert ashby_raw.external_id == "enter-ai:abc"
    assert ashby_raw.location == "Remoto no Brasil"
    assert str(ashby_raw.source_url) == ashby_job["jobUrl"]


def test_new_source_validation_allows_description_based_remote_scope(monkeypatch):
    raw = RawJob(
        source="ashby",
        source_url="https://jobs.ashbyhq.com/enter-ai/backend-engineer",
        title="Backend Engineer",
        company="Enter AI",
        description=(
            "We are hiring a backend engineer for a remote role open to candidates "
            "based in Brazil. Applicants should have experience building reliable "
            "distributed systems and collaborating with product teams."
        ),
        location="New York",
        fetched_at="2026-11-24T12:00:00+00:00",
    )
    def fake_check_url_alive(url, source=None, *, require_job_posting=True):
        assert url.startswith("https://jobs.ashbyhq.com/")
        return True, ""

    monkeypatch.setattr(job_validator, "check_url_alive", fake_check_url_alive)

    normalized = normalize_job(raw)

    assert job_validator.validate_job(normalized) == []
    assert normalized.apply_url == str(raw.source_url)
