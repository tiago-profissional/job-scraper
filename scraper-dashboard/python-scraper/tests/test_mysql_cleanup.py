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
    "https://github.com/acme/jobs/issues/201",
    None,
    "Job description",
)
CAREER_PAGE_ROW = (
    43,
    "Backend Engineer",
    "https://careers.example.com/jobs/backend",
    None,
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
        )


def test_cleanup_keeps_github_issue_when_api_check_is_transiently_unavailable():
    with patch(
        "scraper.storage.mysql_store.check_github_issue_job_posting",
        return_value=(False, "github_issue_check_failed"),
    ):
        assert _check_stored_row(GITHUB_ROW) == (42, "Backend Engineer", "")


def test_cleanup_removes_page_that_no_longer_looks_like_a_job():
    with patch(
        "scraper.storage.mysql_store.check_url_alive",
        return_value=(False, "soft_404_no_job_signals"),
    ):
        assert _check_stored_row(CAREER_PAGE_ROW) == (
            43,
            "Backend Engineer",
            "soft_404_no_job_signals",
        )


def test_cleanup_removes_job_with_confirmed_dead_apply_url():
    with patch(
        "scraper.storage.mysql_store.check_url_alive",
        side_effect=[(True, ""), (False, "dead_link_404")],
    ):
        _, _, reason = _check_stored_row(CAREER_PAGE_ROW[:-2] + (
            "https://apply.example.com/backend",
            "Job description",
        ))

    assert reason == "apply_dead_link_404"
    assert _is_confirmed_dead_reason(reason)


@pytest.mark.parametrize(
    "reason",
    ["dead_link_timeout", "dead_link_connection_error", "dead_link_503"],
)
def test_cleanup_keeps_jobs_when_url_recheck_fails_transiently(reason):
    with patch(
        "scraper.storage.mysql_store.check_url_alive",
        return_value=(False, reason),
    ):
        assert _check_stored_row(CAREER_PAGE_ROW) == (43, "Backend Engineer", "")


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
            return 42, row[1], "github_issue_not_valid_job"
        return 43, row[1], "github_issue_check_failed"

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
