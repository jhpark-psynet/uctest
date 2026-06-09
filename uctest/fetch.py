"""uctest fetch — 단일 경기 + 응원글 JSON.

baseball(`--sport B`)은 psynet DATA30 HTTP API (`baseballTotalQuestion`)에서,
그 외 스포츠는 MSSQL stored proc(`LiveScoreDAO`)에서 가져온다. 출력 키는 양쪽 모두
user.jinja 슬롯(`match_info`, `recent_cheers`, `live_board`, `history`)과 일치.

게임 목록(list 모드)은 항상 MSSQL.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from uctest.config import UnifiedChatSettings
from uctest.data30 import baseball as data30_baseball
from uctest.data30.diet import apply_diet
from uctest.data30.client import Data30Client
from uctest.io import write_output
from uctest.livescore import open_dao
from uctest.livescore.dao import LiveScoreDAO

_KST = ZoneInfo("Asia/Seoul")


def _today_kst() -> str:
    return datetime.now(_KST).strftime("%Y%m%d")


def _is_baseball(sport: str) -> bool:
    s = (sport or "").strip().upper()
    return s == "B" or s == "BASEBALL"


class _Data30ClientLike(Protocol):
    async def get_baseball_total_question(self, game_id: str) -> dict[str, Any]: ...


async def do_fetch(
    dao: LiveScoreDAO | None,
    *,
    date: str,
    sport: str,
    game_id: str | None,
    cheer_size: int | None,
    default_cheer_size: int,
    data30: _Data30ClientLike | None = None,
    diet: bool = False,
) -> dict[str, Any]:
    """DAO/Data30Client 호출 + 응답 모양 정리.

    - game_id 없음: MSSQL list 모드 (기존). DAO 필수.
    - game_id 있음 + sport=B + data30 제공: DATA30 경로.
    - game_id 있음 + 그 외: MSSQL 단일 경기 경로. DAO 필수.

    diet=True면 baseball 출력에 입력 다이어트(docs/input_diet.md)를 적용한다 —
    match_info 노이즈 제거 + 스코어/투수 정규화. 비-baseball 출력은 무영향.
    """
    if not game_id:
        if dao is None:
            raise ValueError("list mode requires MSSQL DAO")
        games = await dao.get_games(date, sport)
        return {"date": date, "sport": sport, "games": games}

    if _is_baseball(sport) and data30 is not None:
        raw = await data30.get_baseball_total_question(game_id)
        out = {
            "date": date,
            "sport": sport,
            "game_id": game_id,
            "match_info": data30_baseball.to_match_info(raw),
            "live_board": data30_baseball.to_live_board(raw),
            "recent_cheers": data30_baseball.to_recent_cheers(raw),
            "history": data30_baseball.to_history(raw),
        }
        return apply_diet(out) if diet else out

    if dao is None:
        raise ValueError("MSSQL DAO required for non-baseball single-game fetch")
    size = cheer_size if cheer_size is not None else default_cheer_size
    bundle = await dao.get_game_with_cheers(date, sport, game_id, size)
    out = {
        "date": date,
        "sport": sport,
        "game_id": game_id,
        "match_info": bundle["game"],
        "recent_cheers": bundle["cheers"],
    }
    return apply_diet(out) if diet else out


def add_parser(sub) -> None:
    p = sub.add_parser("fetch", help="livescore 단일 경기 + 응원글 데이터")
    p.add_argument("--date", default=None, help="YYYYMMDD (기본 KST 오늘)")
    p.add_argument("--sport", default="", help="S/B/K/V/H/T 또는 빈 값(전체)")
    p.add_argument("--game-id", default=None,
                   help="단일 게임 + 응원글. 없으면 list 모드(deprecated; uctest games 권장)")
    p.add_argument("--cheer-size", type=int, default=None)
    p.add_argument("--diet", action="store_true",
                   help="입력 다이어트 적용 (docs/input_diet.md): match_info 노이즈 제거 + "
                        "스코어/투수 정규화. baseball에서 입력 토큰 ~10×↓, 환각 감소.")
    p.add_argument("--out", default=None)
    p.add_argument("--no-i18n", action="store_true",
                   help="팀/리그 마스터 i18n 로드 생략 (ID fallback)")
    p.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> int:
    settings = UnifiedChatSettings()
    date = args.date or _today_kst()

    # baseball + game_id가 명확하면 DATA30 단독 경로 (MSSQL 없이도 동작)
    if args.game_id and _is_baseball(args.sport):
        if not settings.data30_base_url or not settings.data30_auth_key:
            print("DATA30_BASE_URL / DATA30_AUTH_KEY 미설정 (baseball fetch 불가)",
                  file=sys.stderr)
            return 3
        client = Data30Client(
            base_url=settings.data30_base_url,
            auth_key=settings.data30_auth_key,
        )

        async def _async_baseball() -> dict[str, Any]:
            return await do_fetch(
                None,
                date=date,
                sport=args.sport,
                game_id=args.game_id,
                cheer_size=args.cheer_size,
                default_cheer_size=settings.livescore_default_cheer_size,
                data30=client,
                diet=args.diet,
            )

        out = asyncio.run(_async_baseball())
        write_output(out, args.out, fmt="json")
        return 0

    # 그 외 경로 — MSSQL
    if not settings.mssql_dsn:
        print("MSSQL_DSN 미설정 (livescore 접근 불가)", file=sys.stderr)
        return 3

    async def _async_main() -> dict[str, Any]:
        async with open_dao(settings, no_i18n=args.no_i18n) as dao:
            return await do_fetch(
                dao,
                date=date,
                sport=args.sport,
                game_id=args.game_id,
                cheer_size=args.cheer_size,
                default_cheer_size=settings.livescore_default_cheer_size,
                diet=args.diet,
            )

    out = asyncio.run(_async_main())
    write_output(out, args.out, fmt="json")
    return 0
