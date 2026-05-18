from __future__ import annotations

import queue
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool

logger = structlog.get_logger()


class DbPool:
    """pyodbc 동기 connection 풀. async 호출은 run_in_threadpool로 감싼다."""

    def __init__(self, dsn: str, size: int = 5):
        self.dsn = dsn
        self.size = size
        self._available: queue.Queue[Any] = queue.Queue(maxsize=size)
        self._created = 0

    def _new_connection(self) -> Any:
        import pyodbc

        return pyodbc.connect(self.dsn, autocommit=True)

    @contextmanager
    def _acquire_sync(self):
        try:
            conn = self._available.get_nowait()
        except queue.Empty:
            if self._created < self.size:
                conn = self._new_connection()
                self._created += 1
            else:
                conn = self._available.get()
        try:
            yield conn
        finally:
            try:
                self._available.put_nowait(conn)
            except queue.Full:
                conn.close()

    async def run(self, fn: Callable[[Any], Any]) -> Any:
        def _exec() -> Any:
            with self._acquire_sync() as conn:
                return fn(conn)

        return await run_in_threadpool(_exec)

    def close_all(self) -> None:
        while not self._available.empty():
            try:
                c = self._available.get_nowait()
                c.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("livescore.pool.close_error", error=str(exc))
