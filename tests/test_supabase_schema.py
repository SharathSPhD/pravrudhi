"""supabase/schema.sql must give every table row-level security and at least one policy, and must
never hardcode a uuid or an email address — the operator promotes the first admin themselves,
after applying the schema, by calling admin_set_role_by_email (see supabase/README.md)."""

from __future__ import annotations

import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "supabase" / "schema.sql"

_CREATE_TABLE_RE = re.compile(r"create table(?:\s+if not exists)?\s+public\.(\w+)", re.IGNORECASE)
_UUID_LITERAL_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_EMAIL_LITERAL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _schema_text() -> str:
    return SCHEMA_PATH.read_text()


def _table_names(schema: str) -> list[str]:
    return _CREATE_TABLE_RE.findall(schema)


def test_schema_declares_at_least_one_table() -> None:
    tables = _table_names(_schema_text())
    assert tables, "expected supabase/schema.sql to declare at least one table"


def test_every_table_enables_row_level_security() -> None:
    schema = _schema_text()
    for table in _table_names(schema):
        pattern = re.compile(rf"alter table public\.{re.escape(table)}\s+enable row level security", re.IGNORECASE)
        assert pattern.search(schema), f"public.{table} has no matching 'enable row level security'"


def test_every_table_has_at_least_one_policy() -> None:
    schema = _schema_text()
    for table in _table_names(schema):
        pattern = re.compile(rf"create policy\b[\s\S]*?\bon public\.{re.escape(table)}\b", re.IGNORECASE)
        assert pattern.search(schema), f"public.{table} has no matching 'create policy ... on public.{table}'"


def test_schema_has_no_literal_uuid() -> None:
    match = _UUID_LITERAL_RE.search(_schema_text())
    assert match is None, f"supabase/schema.sql must not hardcode a uuid, found {match.group(0)!r}"


def test_schema_has_no_literal_email() -> None:
    match = _EMAIL_LITERAL_RE.search(_schema_text())
    assert match is None, f"supabase/schema.sql must not hardcode an email address, found {match.group(0)!r}"
