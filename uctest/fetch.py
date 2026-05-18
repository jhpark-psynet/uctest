"""uctest fetch — livescore MSSQL → 단일 경기 + 응원글 JSON.

unifiedchat 서버를 거치지 않고 LiveScoreDAO를 직접 사용한다. MSSQL_DSN 환경변수
(또는 UnifiedChatSettings.mssql_dsn)가 필요하다.

게임 목록을 보려면 `uctest games`를 쓴다. fetch는 단일 게임 데이터 받기 전용.
호환을 위해 --game-id 없이도 list 모드로 동작하지만 deprecated 경로다.
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
from uctest.livescore.cheer import _extract_cheer_contents
from uctest.livescore.dao import LiveScoreDAO

_KST = ZoneInfo("Asia/Seoul")


def _today_kst() -> str:
    return datetime.now(_KST).strftime("%Y%m%d")


async def do_fetch(
    dao: LiveScoreDAO,
    *,
    date: str,
    sport: str,
    game_id: str | None,
    cheer_size: int | None,
    default_cheer_size: int,
) -> dict[str, Any]:
    """DAO 호출 + 응답 모양 정리. 테스트에서 DAO를 stub으로 갈아끼울 수 있게 분리."""
    if game_id:
        size = cheer_size if cheer_size is not None else default_cheer_size
        bundle = await dao.get_game_with_cheers(date, sport, game_id, size)
        return {
            "date": date,
            "sport": sport,
            "game": bundle["game"],
            "cheers": _extract_cheer_contents(bundle["cheers"]),
        }
    games = await dao.get_games(date, sport)
    return {"date": date, "sport": sport, "games": games}


def add_parser(sub) -> None:
    p = sub.add_parser("fetch", help="livescore 단일 경기 + 응원글 데이터")
    p.add_argument("--date", default=None, help="YYYYMMDD (기본 KST 오늘)")
    p.add_argument("--sport", default="", help="S/B/K/V/H/T 또는 빈 값(전체)")
    p.add_argument("--game-id", default=None,
                   help="단일 게임 + 응원글. 없으면 list 모드(deprecated; uctest games 권장)")
    p.add_argument("--cheer-size", type=int, default=None)
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
            return await do_fetch(
                dao,
                date=date,
                sport=args.sport,
                game_id=args.game_id,
                cheer_size=args.cheer_size,
                default_cheer_size=settings.livescore_default_cheer_size,
            )

    out = asyncio.run(_async_main())
    write_output(out, args.out, fmt="json")
    return 0
