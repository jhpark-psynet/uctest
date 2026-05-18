"""uctest games — livescore 게임 목록 read-only 조회.

에이전트가 어떤 경기가 진행 중인지 보고 `game_id`를 고른 뒤 `uctest fetch
--game-id ...`로 단일 게임 데이터를 받는 흐름의 첫 단계.

DB 호출은 `LiveScoreDAO.get_games` 하나. fetch list 모드와 동일 데이터지만
명령 자체가 "목록 보기"로 분리돼 의도가 명확해진다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from uctest.config import UnifiedChatSettings
from uctest.io import write_output
from uctest.livescore import open_dao
from uctest.livescore.dao import LiveScoreDAO

_KST = ZoneInfo("Asia/Seoul")


def _today_kst() -> str:
    return datetime.now(_KST).strftime("%Y%m%d")


async def do_games(
    dao: LiveScoreDAO,
    *,
    date: str,
    sport: str,
) -> dict[str, Any]:
    """DAO 호출 + 응답 모양 정리. 테스트에서 DAO를 stub으로 갈아끼울 수 있게 분리."""
    games = await dao.get_games(date, sport)
    return {"date": date, "sport": sport, "games": games}


def add_parser(sub) -> None:
    p = sub.add_parser(
        "games",
        help="livescore 게임 목록 (read-only) — 에이전트가 game_id를 고르기 위한 1단계",
    )
    p.add_argument("--date", default=None, help="YYYYMMDD (기본 KST 오늘)")
    p.add_argument("--sport", default="", help="S/B/K/V/H/T 또는 빈 값(전체)")
    p.add_argument("--out", default=None)
    p.add_argument("--no-i18n", action="store_true",
                   help="팀/리그 마스터 i18n 로드 생략 (ID fallback)")
    p.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> int:
    settings = UnifiedChatSettings()
    if not settings.mssql_dsn:
        print("MSSQL_DSN 미설정 (livescore 접근 불가)", file=sys.stderr)
        return 3
    date = args.date or _today_kst()

    async def _async_main() -> dict[str, Any]:
        async with open_dao(settings, no_i18n=args.no_i18n) as dao:
            return await do_games(dao, date=date, sport=args.sport)

    out = asyncio.run(_async_main())
    write_output(out, args.out, fmt="json")
    return 0
