from unittest.mock import MagicMock, patch

import pytest

from scraper.storage.mysql_store import (
    _check_stored_row,
    _is_confirmed_dead_reason,
    cleanup_dead_jobs,
)

GITHUB_ROW = (
    42,
    "Backend Engineer",
    "arbeitnow",
    "https://github.com/acme/jobs/issues/201",
    None,
    "Job description",
)
CAREER_PAGE_ROW = (
    43,
    "Backend Engineer",
    "remotive",
    "https://careers.example.com/jobs/backend",
    "https://apply.example.com/backend",
    "Job description",
)


def test_cleanup_marks_invalid_github_issue_for_removal():
    with patch(
        "scraper.storage.mysql_store.check_github_issue_job_posting",
        return_value=(False, "github_issue_not_valid_job"),
    ):
        assert _check_stored_row(GITHUB_ROW) == (
            42,
            "Backend Engineer",
            "github_issue_not_valid_job",
            None,
        )


def test_cleanup_keeps_github_issue_when_api_check_is_transiently_unavailable():
    with patch(
        "scraper.storage.mysql_store.check_github_issue_job_posting",
        return_value=(False, "github_issue_check_failed"),
    ):
        assert _check_stored_row(GITHUB_ROW) == (42, "Backend Engineer", "", None)


def test_cleanup_removes_page_that_no_longer_looks_like_a_job():
    with patch(
        "scraper.storage.mysql_store.check_url_alive",
        return_value=(False, "soft_404_no_job_signals"),
    ):
        assert _check_stored_row(CAREER_PAGE_ROW) == (
            43,
            "Backend Engineer",
            "soft_404_no_job_signals",
            None,
        )


def test_cleanup_removes_job_with_confirmed_dead_apply_url():
    with patch(
        "scraper.storage.mysql_store.check_url_alive",
        side_effect=[(True, ""), (False, "dead_link_404")],
    ):
        _, _, reason, _ = _check_stored_row(CAREER_PAGE_ROW)

    assert reason == "apply_dead_link_404"
    assert _is_confirmed_dead_reason(reason)


@pytest.mark.parametrize(
    "reason",
    ["dead_link_timeout", "dead_link_connection_error", "dead_link_503"],
)
def test_cleanup_keeps_jobs_when_url_recheck_fails_transiently(reason):
    with patch(
        "scraper.storage.mysql_store.check_url_alive",
        side_effect=[(False, reason)],
    ):
        assert _check_stored_row(CAREER_PAGE_ROW) == (
            43,
            "Backend Engineer",
            "",
            None,
        )


def test_cleanup_passes_source_to_url_validator():
    with patch(
        "scraper.storage.mysql_store.check_url_alive",
        side_effect=[(True, ""), (True, "")],
    ) as check_url:
        _check_stored_row(CAREER_PAGE_ROW)

    assert check_url.call_args_list[0].kwargs == {"source": "remotive"}


def test_cleanup_removes_stored_job_without_apply_url():
    row = CAREER_PAGE_ROW[:2] + (
        "unknown",
        CAREER_PAGE_ROW[3],
        None,
        "Description without application link.",
    )
    with patch(
        "scraper.storage.mysql_store.check_url_alive",
        return_value=(True, ""),
    ):
        result = _check_stored_row(row)

    assert result == (43, "Backend Engineer", "missing_apply_url", None)
    assert _is_confirmed_dead_reason(result[2])


def test_cleanup_uses_source_url_for_known_source_without_apply_url():
    row = CAREER_PAGE_ROW[:4] + (None, CAREER_PAGE_ROW[5])
    with patch(
        "scraper.storage.mysql_store.check_url_alive",
        return_value=(True, ""),
    ):
        result = _check_stored_row(row)

    assert result == (43, "Backend Engineer", "", row[3])


def test_cleanup_does_not_confirm_transient_apply_failures():
    assert not _is_confirmed_dead_reason("apply_dead_link_timeout")


def test_cleanup_deletes_only_rows_with_confirmed_invalidity():
    rows = [GITHUB_ROW, CAREER_PAGE_ROW]
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor

    def recheck(row):
        if row[0] == 42:
            return 42, row[1], "github_issue_not_valid_job", None
        return 43, row[1], "github_issue_check_failed", None

    with (
        patch("scraper.storage.mysql_store.get_db_connection", return_value=connection),
        patch("scraper.storage.mysql_store._ensure_schema"),
        patch("scraper.storage.mysql_store._check_stored_row", side_effect=recheck),
    ):
        cleanup_dead_jobs(max_workers=1)

    delete_call = next(
        call for call in cursor.execute.call_args_list
        if call.args[0].startswith("DELETE FROM jobs")
    )
    assert delete_call.args[1] == [42]


def test_cleanup_persists_inferred_external_apply_url():
    inferred_url = "https://careers.example.com/backend"
    row = GITHUB_ROW[:4] + (
        GITHUB_ROW[3],
        "Apply here: " + inferred_url,
    )
    cursor = MagicMock()
    cursor.fetchall.return_value = [row]
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor

    with (
        patch("scraper.storage.mysql_store.get_db_connection", return_value=connection),
        patch("scraper.storage.mysql_store._ensure_schema"),
        patch(
            "scraper.storage.mysql_store.check_github_issue_job_posting",
            return_value=(True, ""),
        ),
        patch(
            "scraper.storage.mysql_store.check_url_alive",
            return_value=(True, ""),
        ),
    ):
        cleanup_dead_jobs(max_workers=1)

    cursor.executemany.assert_called_once_with(
        "UPDATE jobs SET apply_url = %s WHERE id = %s",
        [(inferred_url, 42)],
    )
