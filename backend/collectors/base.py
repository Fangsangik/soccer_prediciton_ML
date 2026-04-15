"""Abstract base class for all data collectors."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import duckdb


class BaseCollector(ABC):
    """Every collector must implement collect → transform → load."""

    name: str = "base"

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self.conn = conn
        self._run_id: int | None = None

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def collect(self) -> Any:
        """Fetch raw data from the external source (API, file, web).

        Returns:
            Raw data in whatever format the source provides.
        """

    @abstractmethod
    def transform(self, raw: Any) -> list[dict[str, Any]]:
        """Convert raw data into a list of dicts ready for loading.

        Args:
            raw: The value returned by :meth:`collect`.

        Returns:
            A list of record dicts matching the target table schema.
        """

    @abstractmethod
    def load(self, records: list[dict[str, Any]]) -> int:
        """Persist *records* to DuckDB and return the number of rows written.

        Args:
            records: The list returned by :meth:`transform`.

        Returns:
            Number of records successfully inserted/upserted.
        """

    # ------------------------------------------------------------------
    # Convenience runner
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Execute the full ETL pipeline and return the record count.

        Logs a row to ``collector_runs`` with timing and status information.
        """
        started_at = datetime.utcnow()
        self._log_start(started_at)
        try:
            raw = self.collect()
            records = self.transform(raw)
            count = self.load(records)
            self._log_finish(started_at, count, status="success")
            return count
        except Exception as exc:  # noqa: BLE001
            self._log_finish(started_at, 0, status="error", error=str(exc))
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_start(self, started_at: datetime) -> None:
        try:
            result = self.conn.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM collector_runs"
            ).fetchone()
            self._run_id = result[0] if result else 1
            self.conn.execute(
                """
                INSERT INTO collector_runs
                    (id, collector_name, started_at, status)
                VALUES (?, ?, ?, 'running')
                """,
                [self._run_id, self.name, started_at],
            )
        except Exception:  # noqa: BLE001
            pass  # Non-critical — don't abort the run

    def _log_finish(
        self,
        started_at: datetime,
        records_fetched: int,
        *,
        status: str,
        error: str | None = None,
    ) -> None:
        if self._run_id is None:
            return
        finished_at = datetime.utcnow()
        try:
            self.conn.execute(
                """
                UPDATE collector_runs
                SET finished_at = ?,
                    records_fetched = ?,
                    status = ?,
                    error_message = ?
                WHERE id = ?
                """,
                [finished_at, records_fetched, status, error, self._run_id],
            )
        except Exception:  # noqa: BLE001
            pass
