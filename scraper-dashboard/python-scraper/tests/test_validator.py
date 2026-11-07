from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import httpx
from scraper.validation.job_validator import split_valid_invalid, validate_job, _is_link_alive
from scraper.models.job import NormalizedJob

import pytest
@pytest.fixture(autouse=True)
def mock_all_network_requests():
    """Intercepts httpx.head globally so normal tests do not make real internet calls."""
    with patch("scraper.validation.job_validator.httpx.head") as mock_head:
        mock_head.return_value.status_code = 200
        yield mock_head



@patch("scraper.validation.job_validator.httpx.head")
def test_link_returns_true_for_200(mock_head):
    mock_head.return_value.status_code = 200
    assert _is_link_alive("https://adzuna.com.br/valid") is True

@patch("scraper.validation.job_validator.httpx.head")
def test_link_returns_false_for_404(mock_head):
    mock_head.return_value.status_code = 404
    assert _is_link_alive("https://adzuna.com.br/notfound") is False


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
        description="Vaga para desenvolvedor Python com experiência em APIs REST e testes.",
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