"""Thin wrapper around the Postgres connection.

This is the only place in the project that talks to `psycopg` directly.
Anything that needs DB access should go through a repository (see
`repository/commerce_repository.py`) instead of importing this module.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from it_man.config import get_settings


class PostgresStore:
    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url or get_settings().database_url

    @contextmanager
    def cursor(self) -> Iterator[psycopg.Cursor]:
        with (
            psycopg.connect(self._database_url) as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            yield cur

    def fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        with self.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        with self.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
