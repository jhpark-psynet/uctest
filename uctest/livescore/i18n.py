"""LiveScore 마스터 테이블 i18n 캐시.

`TB_LS_GAME_TEAM` / `TB_LS_GAME_LEAGUE` 마스터 테이블을 startup 1회 SELECT로
메모리에 로드해 ID → 한글명 매핑을 제공한다. SP 신설 없이 livescore 응답의
팀명·리그명 fallback 갭을 메우기 위한 정책 예외 — 이 두 SELECT 외 다른 직접
쿼리는 추가하지 않는다.

설계:
- 캐시 lookup은 sync (dict.get) — 호출 hot path에 부담 없음
- 로드는 async (DbPool.run 사용) — pyodbc는 sync지만 threadpool로 감쌈
- 재로드 시 atomic dict swap — 부분 상태 노출 안 함
- 빈 ID/이름 row는 무시 — 마스터 테이블 정합성 방어
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from uctest.livescore.pool import DbPool

logger = structlog.get_logger()


_TEAM_SQL = (
    "SELECT TEAM_ID, NAME FROM dbo.TB_LS_GAME_TEAM WITH(NOLOCK)"
)
_LEAGUE_SQL = (
    "SELECT LEAGUE_ID, NAME FROM dbo.TB_LS_GAME_LEAGUE WITH(NOLOCK)"
)


def _str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    return "" if s == "None" else s


class LiveScoreI18n:
    """팀/리그 ID → 한글명 매핑 캐시."""

    def __init__(self) -> None:
        self._teams: dict[str, str] = {}
        self._leagues: dict[str, str] = {}

    def team_name(self, team_id: str) -> str:
        if not team_id:
            return ""
        return self._teams.get(team_id, "")

    def league_name(self, league_id: str) -> str:
        if not league_id:
            return ""
        return self._leagues.get(league_id, "")

    def set_team(self, team_id: str, name: str) -> None:
        if team_id and name:
            self._teams[team_id] = name

    def set_league(self, league_id: str, name: str) -> None:
        if league_id and name:
            self._leagues[league_id] = name

    async def load_from_pool(self, pool: "DbPool") -> None:
        """마스터 테이블 두 곳을 SELECT해서 캐시를 통째로 교체."""

        def _run(conn: Any) -> tuple[dict[str, str], dict[str, str]]:
            cur = conn.cursor()
            try:
                cur.execute(_TEAM_SQL)
                teams: dict[str, str] = {}
                for row in cur.fetchall():
                    tid = _str(row[0])
                    name = _str(row[1])
                    if tid and name:
                        teams[tid] = name

                cur.execute(_LEAGUE_SQL)
                leagues: dict[str, str] = {}
                for row in cur.fetchall():
                    lid = _str(row[0])
                    name = _str(row[1])
                    if lid and name:
                        leagues[lid] = name

                return teams, leagues
            finally:
                cur.close()

        teams, leagues = await pool.run(_run)
        # atomic swap — 한 시점에 옛/새 캐시가 섞이지 않게
        self._teams = teams
        self._leagues = leagues
        logger.info(
            "livescore.i18n.loaded",
            teams=len(teams),
            leagues=len(leagues),
        )
