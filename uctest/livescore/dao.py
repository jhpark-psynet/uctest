from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

import structlog

from uctest.livescore.i18n import LiveScoreI18n
from uctest.livescore.pool import DbPool
from uctest.livescore.sp import SpParam, call_sp_sync

logger = structlog.get_logger()


_CODE_TO_COMPE = {
    "S": "soccer", "B": "baseball", "K": "basketball",
    "V": "volleyball", "H": "hockey", "T": "tennis",
}


def _json_safe(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, time):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k.lower(): _json_safe(v) for k, v in r.items()} for r in rows]


def _str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    return "" if s == "None" else s


def _default_league_name(compe: str) -> str:
    c = (compe or "").lower()
    return {
        "soccer": "축구", "baseball": "야구", "basketball": "농구",
        "volleyball": "배구", "hockey": "하키", "icehockey": "하키",
        "tennis": "테니스", "golf": "골프", "esports": "e스포츠",
    }.get(c, compe or "")


def _convert_status(state: str) -> str:
    if not state:
        return "UPCOMING"
    return {
        "B": "UPCOMING", "D": "UPCOMING", "1": "UPCOMING",
        "I": "LIVE", "S": "LIVE", "U": "LIVE", "2": "LIVE",
        "E": "FINISHED", "F": "FINISHED", "O": "FINISHED",
        "3": "FINISHED", "FT": "FINISHED",
        "C": "CANCELLED",
    }.get(state, "UPCOMING")


def _correct_status_by_text(status: str, state_txt: str) -> str:
    if not state_txt:
        return status
    txt = state_txt.strip()
    end_keys = ("종", "END", "FINAL", "FT", "종료", "경기종료", "GAME SET",
                "GAME OVER", "MATCH END", "종 료")
    if any(k in txt or txt.upper() == k.upper() for k in end_keys):
        return "FINISHED"
    if any(k in txt for k in ("회", "쿼터", "세트", "반", "진행", "LIVE", "HT")):
        return "LIVE"
    return status


def _build_game_json(
    *,
    game_id: str,
    compe: str,
    home_team: str,
    away_team: str,
    home_score: str,
    away_score: str,
    state: str,
    state_txt: str,
    match_date: str,
    match_time: str,
    league_name: str,
    today: str,
    home_team_id: str,
    away_team_id: str,
    league_id: str = "",
    i18n: LiveScoreI18n | None = None,
) -> dict[str, Any]:
    status = _convert_status(state)
    if status == "UPCOMING" and state_txt:
        status = _correct_status_by_text(status, state_txt)

    if state in ("B", "D"):
        home_score = ""
        away_score = ""

    status_text = state_txt or ""
    if status == "FINISHED":
        if (not status_text
                or any(k in status_text for k in ("회", "쿼터", "세트", "반"))):
            status_text = "종료"
    elif not status_text:
        if status == "LIVE":
            status_text = "진행 중"
        elif status == "UPCOMING":
            status_text = "예정"
        elif status == "CANCELLED":
            status_text = "취소"

    start_time = ""
    if match_time:
        if ":" in match_time:
            start_time = match_time
        elif len(match_time) >= 4:
            start_time = f"{match_time[0:2]}:{match_time[2:4]}"
        else:
            start_time = match_time

    date_label = ""
    if match_date and len(match_date) == 8 and match_date != today:
        date_label = f"{match_date[4:6]}/{match_date[6:8]} "

    if not league_name and league_id and i18n is not None:
        league_name = i18n.league_name(league_id)
    if not league_name:
        league_name = _default_league_name(compe)
    if not home_team and home_team_id:
        home_team = (i18n.team_name(home_team_id) if i18n is not None else "") or home_team_id
    elif not home_team:
        home_team = ""
    if not away_team and away_team_id:
        away_team = (i18n.team_name(away_team_id) if i18n is not None else "") or away_team_id
    elif not away_team:
        away_team = ""

    return {
        "game_id": game_id or "",
        "compe": compe or "",
        "league_name": league_name,
        "home_team": home_team,
        "away_team": away_team,
        "home_team_id": home_team_id or "",
        "away_team_id": away_team_id or "",
        "home_score": home_score,
        "away_score": away_score,
        "status": status,
        "status_text": status_text,
        "start_time": date_label + start_time,
        "match_date": match_date or "",
        "match_time": match_time or "",
    }


def _parse_game_map(
    row: dict[str, Any],
    today: str,
    i18n: LiveScoreI18n | None = None,
) -> dict[str, Any] | None:
    r = {k.lower(): v for k, v in row.items()}
    if _str(r.get("game_type")) == "G":  # exclude mini-game / banner rows
        return None

    return _build_game_json(
        game_id=_str(r.get("game_id")),
        compe=_str(r.get("compe")),
        home_team=_str(r.get("home_team_name")),
        away_team=_str(r.get("away_team_name")),
        home_score=_str(r.get("home_score")),
        away_score=_str(r.get("away_score")),
        state=_str(r.get("state")),
        state_txt=_str(r.get("state_txt")),
        match_date=_str(r.get("match_date")),
        match_time=_str(r.get("match_time")),
        league_name="",
        today=today,
        home_team_id=_str(r.get("home_team_id")),
        away_team_id=_str(r.get("away_team_id")),
        league_id=_str(r.get("league_id")),
        i18n=i18n,
    )


def normalize_sport(sport: str) -> str:
    """B/S/K/V/H/T 코드 또는 soccer/baseball/... → 정규화된 compe 문자열.

    빈 값이면 빈 문자열 그대로 (SP에서 '전체' 의미)."""
    s = (sport or "").strip()
    if not s:
        return ""
    if len(s) <= 2 and s.upper() in _CODE_TO_COMPE:
        return _CODE_TO_COMPE[s.upper()]
    return s.lower()


class LiveScoreDAO:
    """라이브스코어 MSSQL stored procedure fetcher."""

    def __init__(self, pool: DbPool, i18n: LiveScoreI18n | None = None):
        self.pool = pool
        self.i18n = i18n if i18n is not None else LiveScoreI18n()

    async def get_games(self, date_yyyymmdd: str, sport: str = "") -> list[dict[str, Any]]:
        today = date_yyyymmdd
        compe = normalize_sport(sport)
        i18n = self.i18n

        def _run(conn: Any) -> list[dict[str, Any]]:
            r = call_sp_sync(
                conn,
                "dbo.SP_TB_LS_GAME_LIST_BETTING_PHRASE_NEW",
                [
                    SpParam("search_date", date_yyyymmdd),
                    SpParam("user_no", 0),
                    SpParam("compe", compe),
                    SpParam("country_code", "KR"),
                    SpParam("gmt_hh", "+0900"),
                    SpParam("language_code", "KO"),
                    SpParam("s_date", ""),
                    SpParam("e_date", ""),
                ],
                out_specs=[],
            )
            out: list[dict[str, Any]] = []
            for row in r.rows:
                g = _parse_game_map(row, today, i18n=i18n)
                if g is None:
                    continue
                md = g.get("match_date", "")
                if md and md != today:
                    continue
                out.append(g)
            return out

        try:
            return await self.pool.run(_run)
        except Exception as e:  # noqa: BLE001
            logger.error("livescore.get_games.error", date=date_yyyymmdd, sport=sport, error=str(e))
            return []

    async def get_cheers(
        self, game_id: str, compe: str, page_size: int = 30
    ) -> list[dict[str, Any]]:
        normalized = normalize_sport(compe)

        def _run(conn: Any) -> list[dict[str, Any]]:
            r = call_sp_sync(
                conn,
                "dbo.SP_TB_LS_CHEER_BOARD_SELECT_NEW",
                [
                    SpParam("game_id", game_id),
                    SpParam("compe", normalized),
                    SpParam("next_key", ""),
                    SpParam("page_size", int(page_size) if page_size else 30),
                    SpParam("user_no", 0),
                    SpParam("search_country_code", ""),
                    SpParam("search_flag", ""),
                    SpParam("pre_next_flag", ""),
                    SpParam("include_gift", 0),
                ],
                out_specs=[],
            )
            return _normalize_rows(r.rows)

        try:
            return await self.pool.run(_run)
        except Exception as e:  # noqa: BLE001
            logger.error("livescore.get_cheers.error", game_id=game_id, error=str(e))
            return []

    async def get_game_with_cheers(
        self,
        date_yyyymmdd: str,
        sport: str,
        game_id: str,
        cheer_size: int = 30,
    ) -> dict[str, Any]:
        games = await self.get_games(date_yyyymmdd, sport)
        match = next((g for g in games if g.get("game_id") == game_id), None)
        if match is None:
            return {"game": None, "cheers": []}
        cheers = await self.get_cheers(game_id, match.get("compe", sport), cheer_size)
        return {"game": match, "cheers": cheers}
