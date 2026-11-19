from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from scraper.fetching.http_client import check_url_alive
from scraper.models.job import NormalizedJob
from scraper.validation.job_validator import split_valid_invalid, validate_job


@pytest.fixture(autouse=True)
def mock_all_network_requests():
    """Intercepts HTTP requests so validator tests never access the network."""
    with patch("scraper.fetching.http_client.httpx.get") as mock_get:
        def successful_get(url: str, **kwargs):
            response = Mock(status_code=200, url=url, text="")
            response.headers = {"Content-Type": "application/json"}
            return response

        mock_get.side_effect = successful_get
        yield mock_get


@patch("scraper.fetching.http_client.httpx.get")
def test_link_returns_true_for_200(mock_get):
    url = "https://adzuna.com.br/valid"
    response = Mock(status_code=200, url=url, text="")
    response.headers = {"Content-Type": "application/json"}
    mock_get.return_value = response

    assert check_url_alive(url, source="adzuna") == (True, "")
    mock_get.assert_called_once()


@patch("scraper.fetching.http_client.httpx.get")
def test_link_returns_false_for_404(mock_get):
    url = "https://adzuna.com.br/notfound"
    mock_get.return_value = Mock(status_code=404)

    assert check_url_alive(url, source="adzuna") == (False, "dead_link_404")
    mock_get.assert_called_once()


def make_job(**changes) -> NormalizedJob:
    """A valid job. Each test changes only the field it is testing.

    model_construct skips Pydantic validation, so we can build jobs the
    model itself would refuse (for example, one with no title).
    """
    base = dict(
        source="adzuna",
        source_url="https://www.adzuna.com.br/details/5913094087",
        title="Desenvolvedor Python Júnior",
        company="Empresa X",
        description=(
            "Vaga para desenvolvedor Python com experiência em APIs REST e testes, "
            "com colaboração diária em equipe multidisciplinar."
        ),
        apply_url="https://apply.example.com/backend",
        published_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    base.update(changes)
    return NormalizedJob.model_construct(**base)


# Valid job

def test_valid_job_has_no_reasons():
    assert validate_job(make_job()) == []


# Required fields

def test_missing_title():
    assert "missing_title" in validate_job(make_job(title=""))


def test_generic_title():
    assert "generic_title" in validate_job(make_job(title="Vagas"))


def test_missing_company():
    assert "missing_company" in validate_job(make_job(company=None))


def test_missing_description():
    assert "missing_description" in validate_job(make_job(description=""))


def test_short_description():
    assert "description_too_short" in validate_job(make_job(description="Vaga curta"))


# URL

def test_missing_url():
    assert "missing_url" in validate_job(make_job(source_url=None))


def test_relative_url_is_invalid():
    assert "invalid_url" in validate_job(make_job(source_url="/details/123"))


def test_unknown_source():
    assert "source_not_allowed" in validate_job(make_job(source="unknown_site"))


def test_wrong_domain():
    job = make_job(source_url="https://www.example.com/details/123")
    assert "domain_not_allowed" in validate_job(job)


def test_missing_apply_url_uses_non_github_source_url():
    job = make_job(
        apply_url=None,
        description=(
            "Vaga para desenvolvimento de software com responsabilidades e requisitos "
            "descritos em detalhes, mas sem nenhum endereço externo de candidatura."
        ),
    )

    assert validate_job(job) == []
    assert job.apply_url == str(job.source_url)


def test_github_apply_url_is_rejected():
    job = make_job(apply_url="https://github.com/acme/jobs/issues/201")

    assert "apply_url_points_to_github" in validate_job(job)


@patch("scraper.validation.job_validator.check_url_alive", return_value=(True, ""))
def test_application_url_is_checked_without_job_posting_signals(mock_check_url):
    job = make_job(apply_url="https://apply.example.com/backend")

    assert validate_job(job) == []
    assert mock_check_url.call_args_list[1].args == (
        "https://apply.example.com/backend",
    )
    assert mock_check_url.call_args_list[1].kwargs == {
        "require_job_posting": False,
    }


def test_subdomain_is_allowed():
    job = make_job(source_url="https://br.adzuna.com.br/details/123")
    assert validate_job(job) == []


# Page type

def test_login_page():
    job = make_job(source_url="https://www.adzuna.com.br/login")
    assert validate_job(job) == ["login_page"]


def test_search_page():
    job = make_job(source_url="https://www.adzuna.com.br/search")
    assert validate_job(job) == ["search_page"]


def test_not_a_job_page():
    job = make_job(source_url="https://www.adzuna.com.br/empresas/empresa-x")
    assert validate_job(job) == ["not_a_job_page"]


# Date

def test_published_in_future():
    future = datetime.now(timezone.utc) + timedelta(days=3)
    assert "published_in_future" in validate_job(make_job(published_at=future))


def test_tomorrow_is_tolerated():
    soon = datetime.now(timezone.utc) + timedelta(hours=12)
    assert validate_job(make_job(published_at=soon)) == []


def test_missing_date_is_allowed():
    assert validate_job(make_job(published_at=None)) == []


# Split

def test_split_valid_invalid():
    good = make_job()
    bad = make_job(title="", company=None)

    valid, invalid = split_valid_invalid([good, bad])

    assert valid == [good]
    assert len(invalid) == 1
    job, reasons = invalid[0]
    assert job is bad
    assert reasons == ["missing_title", "missing_company"]