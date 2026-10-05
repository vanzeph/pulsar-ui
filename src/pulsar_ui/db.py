"""A guarded, read-only DuckDB entry point.

The UI design fixes the read-path baseline: "纯只读：无任何写接口；
DuckDB 以只读模式打开；UI 永不修改数据湖与工件". :class:`ReadOnlyDuckDB`
implements that twice over:

* every connection is in-memory (``:memory:``) — there is no DuckDB
  database file to write to, and the Parquet lake is only ever *scanned*
  through ``read_parquet`` table functions;
* :meth:`ReadOnlyDuckDB.query` refuses any statement that is not a single
  ``SELECT``/``WITH`` — the same guard pulsar-data's query layer uses —
  so no mis-formed call can mutate anything, even in memory.

Connections are per-use (entered via ``with``): FastAPI runs sync
endpoints on a thread pool, and per-call connections make concurrent
requests trivially safe without shared mutable state. The SQL text always
comes from this package's own constants; user input only ever reaches the
engine as bound ``?`` parameters.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import TracebackType
from typing import Any

import duckdb

__all__ = ["ReadOnlyDuckDB", "ReadonlyViolation"]

#: Statement prefixes the read layer allows (case-insensitive).
_ALLOWED_PREFIXES = ("select", "with")


class ReadonlyViolation(RuntimeError):
    """Raised when a statement would leave the read-only contract."""


class ReadOnlyDuckDB:
    """One guarded in-memory DuckDB session over the local Parquet world."""

    def __init__(self) -> None:
        self._connection: duckdb.DuckDBPyConnection | None = None

    # -- context manager ------------------------------------------------------

    def __enter__(self) -> ReadOnlyDuckDB:  # noqa: PYI034 - Self needs 3.11+ typing import; keep it simple
        self._connection = duckdb.connect(":memory:")
        self._connection.execute("SET TimeZone='Asia/Shanghai'")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # -- execution ------------------------------------------------------------

    @staticmethod
    def _guard(sql: str) -> str:
        """Reject anything that is not a single read-only statement."""
        text = sql.strip().rstrip(";").strip()
        if not text or ";" in text:
            raise ReadonlyViolation("read layer accepts exactly one statement per call")
        if not text.lower().startswith(_ALLOWED_PREFIXES):
            raise ReadonlyViolation(
                "read layer is read-only: only SELECT/WITH statements are allowed"
            )
        return text

    def query(
        self, sql: str, params: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run one guarded SELECT/WITH and return rows as plain dicts."""
        if self._connection is None:  # pragma: no cover - misuse guard
            raise RuntimeError("ReadOnlyDuckDB must be used as a context manager")
        statement = self._guard(sql)
        cursor = self._connection.execute(statement, list(params) if params else [])
        columns = [description[0] for description in cursor.description or []]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
