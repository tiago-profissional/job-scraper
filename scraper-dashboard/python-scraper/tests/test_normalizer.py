import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scraper.models.job import EmploymentType, RawJob, Seniority, WorkMode
from scraper.normalization.job_normalizer import (
    clean_company,
    clean_description,
    clean_text,
    clean_title,
    extract_external_apply_url,
    normalize_date,
    normalize_employment_type,
    normalize_job,
    normalize_seniority,
    normalize_technologies,
    normalize_work_mode,
    split_location,
)
from scraper.sources.adzuna import AdzunaAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "adzuna_sample.json"


def test_clean_text():
    assert clean_text("  Desenvolvedor    Python  \n") == "Desenvolvedor Python"


def test_employment_type_unknown_is_none():
    assert normalize_employment_type("banana") is None
    assert normalize_employment_type("full_time") == EmploymentType.FULL_TIME


def test_seniority_junior():
    assert normalize_seniority("Desenvolvedor Python Júnior") == Seniority.JUNIOR


def test_seniority_senior():
    assert normalize_seniority("Desenvolvedor Python Sênior") == Seniority.SENIOR


def test_seniority_unknown_is_none():
    assert normalize_seniority("Desenvolvedor Python") is None
    assert normalize_seniority(None) is None


def test_seniority_mid_level():
    assert normalize_seniority("Desenvolvedor Python Pleno") == Seniority.MID_LEVEL


def test_clean_title_removes_extra_spaces():
    assert clean_title("  Desenvolvedor   Java \n") == "Desenvolvedor Java"


def test_clean_company_empty_becomes_none():
    assert clean_company("") is None
    assert clean_company(None) is None
    assert clean_company("  8IT ") == "8IT"


def test_paragraphs_are_kept_as_blank_lines():
    assert clean_description("<p>Um.</p><p>Dois.</p>") == "Um.\n\nDois."


def test_br_becomes_line_break():
    assert clean_description("A<br>B<br/>C") == "A\nB\nC"


def test_inline_tags_do_not_split_words():
    assert clean_description("<p>Vaga de <b>Python</b>, <a href='x'>Django</a>.</p>") == "Vaga de Python, Django."


def test_list_items_become_bullets():
    assert clean_description("<p>Requisitos:</p><ul><li>Python</li><li>SQL</li></ul>") == "Requisitos:\n\n- Python\n- SQL"


def test_script_and_style_are_removed():
    assert clean_description("<style>p{color:red}</style><p>Texto</p><script>alert(1)</script>") == "Texto"


def test_entities_are_decoded():
    assert clean_description("<p>R&amp;D&nbsp;team &lt;3</p>") == "R&D team <3"


def test_plain_text_keeps_its_own_line_breaks():
    assert clean_description("Linha 1\nLinha 2") == "Linha 1\nLinha 2"


def test_source_newlines_inside_html_are_just_spaces():
    assert clean_description("<p>Texto\nquebrado\nno codigo</p>") == "Texto quebrado no codigo"


def test_none_and_empty_return_empty_string():
    assert clean_description(None) == ""
    assert clean_description("") == ""
    assert clean_description("   ") == ""


def test_work_mode_remote():
    assert normalize_work_mode("Desenvolvedor Frontend - Trabalho Remoto") == WorkMode.REMOTE


def test_work_mode_hybrid_wins_over_remote():
    assert normalize_work_mode("Vaga híbrida, 2 dias remoto") == WorkMode.HYBRID


def test_work_mode_onsite():
    assert normalize_work_mode("Desenvolvedor Python presencial") == WorkMode.ONSITE


def test_work_mode_unknown_is_none():
    assert normalize_work_mode("Desenvolvedor Python") is None
    assert normalize_work_mode(None) is None


def test_split_location_city_and_state():
    assert split_location(["Brasil", "Nordeste", "Ceará", "Horizonte"]) == ("Horizonte", "Ceará")


def test_split_location_ignores_neighborhood():
    area = ["Brasil", "Nordeste", "Ceará", "Fortaleza", "Jangurussu"]
    assert split_location(area) == ("Fortaleza", "Ceará")


def test_split_location_state_only():
    assert split_location(["Brasil", "Nordeste", "Ceará"]) == (None, "Ceará")


def test_split_location_missing_or_too_short():
    assert split_location(["Brasil"]) == (None, None)
    assert split_location([]) == (None, None)
    assert split_location(None) == (None, None)


def test_normalize_date_iso_z():
    assert normalize_date("2026-09-30T21:24:33Z") == datetime(2026, 9, 30, 21, 24, 33, tzinfo=timezone.utc)


def test_normalize_date_converts_offset_to_utc():
    result = normalize_date("2026-09-30T18:24:33-03:00")
    assert result == datetime(2026, 9, 30, 21, 24, 33, tzinfo=timezone.utc)
    assert result.utcoffset().total_seconds() == 0  # stored as UTC, not -03:00


def test_normalize_date_invalid_or_missing():
    assert normalize_date("garbage") is None
    assert normalize_date("") is None
    assert normalize_date(None) is None


def test_normalize_job_on_real_fixture():
    items = json.loads(FIXTURE.read_text(encoding="utf-8"))["results"]
    adapter = AdzunaAdapter()
    jobs = [normalize_job(adapter.parse(i)) for i in items]
    assert len(jobs) == 5
    assert (jobs[0].city, jobs[0].state) == ("Horizonte", "Ceará")
    assert jobs[0].company is None
    assert jobs[3].company == "AjaxTI"
    assert jobs[4].city == "Fortaleza"
    assert jobs[0].published_at.year == 2026
    assert jobs[0].raw["title"] == "Desenvolvedor Para Ios"
    
    
def test_normalize_job_extracts_non_ats_application_url():
    raw = RawJob(
        source="arbeitnow",
        source_url="https://github.com/acme/jobs/issues/201",
        title="Backend Engineer",
        company="Acme",
        description="How to apply: [Apply here](https://careers.example.com/backend).",
        fetched_at="2026-11-19T12:00:00Z",
    )

    assert normalize_job(raw).apply_url == "https://careers.example.com/backend"


@pytest.mark.parametrize(
    ("source", "source_url"),
    [
        ("adzuna", "https://www.adzuna.com.br/details/123"),
        ("remotive", "https://remotive.com/remote-jobs/backend/123"),
        ("arbeitnow", "https://www.arbeitnow.com/job/backend-123"),
    ],
)
def test_normalize_job_uses_non_github_source_url_without_ats(source, source_url):
    raw = RawJob(
        source=source,
        source_url=source_url,
        title="Backend Engineer",
        company="Acme",
        description="A sufficiently detailed job description without an ATS link.",
        fetched_at="2026-11-19T12:00:00Z",
    )

    assert str(normalize_job(raw).apply_url) == source_url


def test_github_issue_without_external_url_has_no_apply_url():
    raw = RawJob(
        source="arbeitnow",
        source_url="https://github.com/acme/jobs/issues/201",
        title="Backend Engineer",
        company="Acme",
        description="A job description without an external application link.",
        fetched_at="2026-11-19T12:00:00Z",
    )

    assert normalize_job(raw).apply_url is None


def test_external_apply_url_extraction_rejects_github_and_keeps_linkedin():
    description = (
        "Repo: https://github.com/acme/jobs/issues/1 "
        "Apply: https://www.linkedin.com/jobs/view/123"
    )

    assert extract_external_apply_url(description) == "https://www.linkedin.com/jobs/view/123"


def test_technologies_node_variants():
    assert normalize_technologies("Node JS") == ["Node.js"]
    assert normalize_technologies("nodejs") == ["Node.js"]
    assert normalize_technologies("node.js") == ["Node.js"]


def test_technologies_java_vs_javascript():
    assert normalize_technologies("Vaga JavaScript") == ["JavaScript"]
    assert normalize_technologies("Java e Spring Boot") == ["Java", "Spring"]


def test_technologies_sorted_no_duplicates():
    assert normalize_technologies("Python, python e PYTHON com Django") == ["Django", "Python"]


def test_technologies_symbols():
    assert normalize_technologies("Dev C# .NET") == [".NET", "C#"]


def test_technologies_git_not_github():
    assert normalize_technologies("Git e GitHub") == ["Git"]


def test_technologies_none_or_empty():
    assert normalize_technologies(None) == []
    assert normalize_technologies("") == []
    assert normalize_technologies("Vaga de vendedor") == []


def test_different_spellings_same_standard_values():
    # Step 8 "Concluído quando": different spellings -> same standard value
    assert normalize_work_mode("Trabalho Remoto") == normalize_work_mode("remote") == WorkMode.REMOTE
    assert normalize_seniority("Desenvolvedor Júnior") == normalize_seniority("Junior Developer") == Seniority.JUNIOR
    assert normalize_technologies("Node JS") == normalize_technologies("nodejs") == ["Node.js"]