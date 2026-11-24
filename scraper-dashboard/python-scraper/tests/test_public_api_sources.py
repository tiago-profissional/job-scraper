from scraper.fetching import (
    ashby_client,
    greenhouse_client,
    jooble_client,
    loopcv_client,
    serpapi_client,
    theirstack_client,
)
from scraper.fetching.http_client import get_json, get_json_list, post_json
from scraper.models.job import RawJob
from scraper.normalization.job_normalizer import normalize_job
from scraper.sources.ashby import AshbyAdapter
from scraper.sources.greenhouse import GreenhouseAdapter
from scraper.sources.jooble import JoobleAdapter
from scraper.sources.loopcv import LoopCVAdapter
from scraper.sources.serpapi import SerpApiAdapter
from scraper.sources.theirstack import TheirStackAdapter
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


def test_http_client_supports_post_objects_and_get_arrays(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, value):
            self.value = value

        def raise_for_status(self):
            pass

        def json(self):
            return self.value

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return FakeResponse({"jobs": []})

    def fake_get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return FakeResponse([{"title": "Remote Engineer"}])

    monkeypatch.setattr("scraper.fetching.http_client.httpx.post", fake_post)
    monkeypatch.setattr("scraper.fetching.http_client.httpx.get", fake_get)

    assert post_json(
        "https://api.example.test/search",
        {"keywords": ["TI"]},
        headers={"X-API-KEY": "test-key"},
    ) == {"jobs": []}
    assert get_json_list(
        "https://api.example.test/loop/jobs",
        headers={"X-API-KEY": "test-key"},
    ) == [{"title": "Remote Engineer"}]
    assert calls[0][0:2] == ("POST", "https://api.example.test/search")
    assert calls[0][2]["json"] == {"keywords": ["TI"]}
    assert calls[0][2]["headers"] == {"X-API-KEY": "test-key"}
    assert calls[1][0:2] == ("GET", "https://api.example.test/loop/jobs")


def test_jooble_client_posts_search_to_keyed_endpoint(monkeypatch):
    calls = []
    monkeypatch.setenv("JOOBLE_API_KEY", "test-key")

    def fake_post_json(url, payload, *, max_retries):
        calls.append((url, payload, max_retries))
        return {"jobs": [{"id": 12}]}

    monkeypatch.setattr(jooble_client, "post_json", fake_post_json)

    assert jooble_client.search_jooble_jobs(
        "Estágio TI",
        "Ceará",
        max_retries=2,
    ) == {"jobs": [{"id": 12}]}
    assert calls == [
        (
            "https://jooble.org/api/test-key",
            {"keywords": "Estágio TI", "location": "Ceará"},
            2,
        )
    ]


def test_serpapi_client_uses_google_jobs_query(monkeypatch):
    calls = []
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")

    def fake_get_json(url, *, params, max_retries):
        calls.append((url, params, max_retries))
        return {"jobs_results": [{"job_id": "job-1"}]}

    monkeypatch.setattr(serpapi_client, "get_json", fake_get_json)

    assert serpapi_client.search_google_jobs("Estágio TI") == {
        "jobs": [{"job_id": "job-1"}]
    }
    assert calls == [
        (
            "https://serpapi.com/search.json",
            {
                "api_key": "test-key",
                "engine": "google_jobs",
                "q": "Estágio TI",
                "location": "Brazil",
                "gl": "br",
                "hl": "pt",
            },
            3,
        )
    ]


def test_loopcv_client_fetches_jobs_for_existing_loop(monkeypatch):
    calls = []
    monkeypatch.setenv("LOOPCV_API_KEY", "test-key")
    monkeypatch.setenv("LOOPCV_LOOP_ID", "loop-1")

    def fake_get_json_list(url, *, headers, max_retries):
        calls.append((url, headers, max_retries))
        return [{"_id": "job-1"}]

    monkeypatch.setattr(loopcv_client, "get_json_list", fake_get_json_list)

    assert loopcv_client.search_loopcv_jobs() == [{"_id": "job-1"}]
    assert calls == [
        (
            "https://b2b-api.loopcv.com/connect/loop/loop-1/jobs",
            {"X-API-KEY": "test-key"},
            3,
        )
    ]


def test_theirstack_client_uses_brazil_and_recent_posting_filters(monkeypatch):
    calls = []
    monkeypatch.setenv("THEIRSTACK_API_KEY", "test-key")

    def fake_post_json(url, payload, *, headers, max_retries):
        calls.append((url, payload, headers, max_retries))
        return {"data": [{"id": 9}]}

    monkeypatch.setattr(theirstack_client, "post_json", fake_post_json)

    assert theirstack_client.search_theirstack_jobs(limit=3) == {
        "jobs": [{"id": 9}]
    }
    assert calls == [
        (
            "https://api.theirstack.com/v1/jobs/search",
            {
                "job_title_or": theirstack_client.DEFAULT_JOB_TITLES,
                "job_country_code_or": ["BR"],
                "posted_at_max_age_days": 30,
                "limit": 3,
                "page": 0,
                "include_total_results": False,
            },
            {"Authorization": "Bearer test-key"},
            3,
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
        assert source == "ashby"
        assert require_job_posting is True
        return True, ""

    monkeypatch.setattr(job_validator, "check_url_alive", fake_check_url_alive)

    normalized = normalize_job(raw)

    assert job_validator.validate_job(normalized) == []
    assert normalized.apply_url == str(raw.source_url)


def test_aggregator_adapters_map_direct_application_urls():
    jooble = JoobleAdapter().parse(
        {
            "id": 12,
            "title": "Suporte Técnico",
            "company": "Empresa",
            "location": "Fortaleza, CE",
            "summary": "Descrição da vaga",
            "link": "https://jobs.example.test/12",
        }
    )
    serpapi = SerpApiAdapter().parse(
        {
            "job_id": "serp-1",
            "title": "Estágio TI",
            "company_name": "Empresa",
            "location": "Recife, Brasil",
            "description": "Descrição da vaga",
            "share_link": "https://www.google.com/search?job=1",
            "apply_options": [{"link": "https://jobs.example.test/serp-1"}],
        }
    )
    loopcv = LoopCVAdapter().parse(
        {
            "_id": "loop-1",
            "title": "Desenvolvedor",
            "company": "Empresa",
            "location": "Remote, Brazil",
            "summary": "Descrição da vaga",
            "url": "https://jobs.example.test/loop-1",
        }
    )
    theirstack = TheirStackAdapter().parse(
        {
            "id": 99,
            "job_title": "Help Desk",
            "company": "Empresa",
            "location": "Natal, RN",
            "description": "Descrição da vaga",
            "url": "https://jobs.example.test/theirstack-99",
            "final_url": "https://careers.example.test/theirstack-99",
        }
    )

    assert jooble.source == "jooble"
    assert jooble.apply_url == "https://jobs.example.test/12"
    assert serpapi.source == "serpapi"
    assert serpapi.apply_url == "https://jobs.example.test/serp-1"
    assert loopcv.source == "loopcv"
    assert loopcv.apply_url == "https://jobs.example.test/loop-1"
    assert theirstack.source == "theirstack"
    assert theirstack.apply_url == "https://careers.example.test/theirstack-99"


def test_aggregator_adapters_filter_jobs_outside_brazil_and_remote_scope(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "test-key")
    monkeypatch.setattr("scraper.sources.jooble.JOOBLE_KEYWORDS", ["Suporte Técnico"])
    monkeypatch.setattr("scraper.sources.jooble.JOOBLE_LOCATIONS", ["Brasil"])
    def fake_search_jooble(keyword, location):
        assert keyword == "Suporte Técnico"
        assert location == "Brasil"
        return {
            "jobs": [
                {"id": 1, "location": "Fortaleza, CE", "summary": "Vaga local"},
                {"id": 2, "location": "Berlin", "summary": "On-site"},
            ]
        }

    monkeypatch.setattr("scraper.sources.jooble.search_jooble_jobs", fake_search_jooble)
    monkeypatch.setattr("scraper.sources.serpapi.SERPAPI_QUERIES", ["Estágio TI"])

    def fake_search_serpapi(query):
        assert query == "Estágio TI"
        return {
            "jobs": [
                {"job_id": "br", "location": "Recife, Brasil", "description": "Estágio"},
                {"job_id": "de", "location": "Berlin", "description": "On-site"},
            ]
        }

    monkeypatch.setattr("scraper.sources.serpapi.search_google_jobs", fake_search_serpapi)
    monkeypatch.setattr(
        "scraper.sources.loopcv.search_loopcv_jobs",
        lambda: [
            {"_id": "remote", "location": "London", "summary": "Remote role"},
            {"_id": "onsite", "location": "Berlin", "summary": "On-site role"},
        ],
    )
    monkeypatch.setattr(
        "scraper.sources.theirstack.search_theirstack_jobs",
        lambda: {
            "jobs": [
                {"id": 1, "location": "Salvador, BA", "description": "Vaga local"},
                {"id": 2, "location": "Berlin", "description": "On-site"},
            ]
        },
    )

    assert [job["id"] for job in JoobleAdapter().discover()] == [1]
    assert [job["job_id"] for job in SerpApiAdapter().discover()] == ["br"]
    assert [job["_id"] for job in LoopCVAdapter().discover()] == ["remote"]
    assert [job["id"] for job in TheirStackAdapter().discover()] == [1]
