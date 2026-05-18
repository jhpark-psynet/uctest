"""livescore — MSSQL DAO·Pool·I18n과 fetch/games 공용 setup 헬퍼.

`open_dao()`는 fetch·games CLI _run이 공유하는 async context manager.
pool 생성·i18n 로드·dao 인스턴스화·종료 시 pool close까지 한곳에서 처리.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog

from uctest.config import UnifiedChatSettings
from uctest.livescore.dao import LiveScoreDAO
from uctest.livescore.i18n import LiveScoreI18n
from uctest.livescore.pool import DbPool


@asynccontextmanager
async def open_dao(
    settings: UnifiedChatSettings,
    *,
    no_i18n: bool = False,
) -> AsyncIterator[LiveScoreDAO]:
    """pool/i18n/dao 셋업 → 사용 → finally pool close.

    i18n 로드 실패는 warning만 찍고 진행 (ID fallback이라 호출 자체는 가능).
    """
    pool = DbPool(settings.mssql_dsn, size=settings.mssql_pool_size)
    i18n = LiveScoreI18n()
    enable_i18n = settings.livescore_i18n_enabled and not no_i18n
    try:
        if enable_i18n:
            try:
                await i18n.load_from_pool(pool)
            except Exception as exc:  # noqa: BLE001
                structlog.get_logger().warning(
                    "uctest.livescore.i18n.load_failed", error=str(exc),
                )
        yield LiveScoreDAO(pool, i18n=i18n)
    finally:
        pool.close_all()
