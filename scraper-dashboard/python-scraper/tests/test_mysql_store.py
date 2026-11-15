from unittest.mock import MagicMock

from scraper.storage.mysql_store import (
    REQUIRED_COLUMNS,
    _ensure_schema,
    _normalize_external_id,
)


def test_ensure_schema_widens_existing_external_id_column():
    column_rows = [
        (name, "varchar(100)" if name == "external_id" else definition.split()[0].lower())
        for name, definition in REQUIRED_COLUMNS.items()
    ]
    cursor = MagicMock()
    cursor.fetchall.return_value = column_rows
    cursor.fetchone.return_value = ("content_hash",)

    _ensure_schema(cursor)

    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert (
        "ALTER TABLE jobs MODIFY COLUMN external_id VARCHAR(255) NULL"
        in executed_sql
    )


def test_external_id_normalization_preserves_long_values_and_removes_padding():
    external_id = "arbeitnow-" + ("job-" * 35)

    assert _normalize_external_id(f"  {external_id}  ") == external_id
    assert len(_normalize_external_id(external_id)) > 100
    assert _normalize_external_id("   ") is None
