"""uctest fetch 단위 테스트 (MSSQL 경로).

LiveScoreDAO를 stub으로 갈아끼고 인자 흐름·출력 모양만 검증한다 (DB 접속 없음).
baseball+DATA30 경로는 test_fetch_baseball_data30.py.
"""
from __future__ import annotations

import pytest

from uctest.fetch import do_fetch


class _StubDAO:
    def __init__(self, games=None, bundle=None):
        self._games = games or []
        self._bundle = bundle or {"game": None, "cheers": []}
        self.calls: list[tuple] = []

    async def get_games(self, date, sport):
        self.calls.append(("get_games", date, sport))
        return self._games

    async def get_game_with_cheers(self, date, sport, game_id, cheer_size):
        self.calls.append(("get_game_with_cheers", date, sport, game_id, cheer_size))
        return self._bundle


@pytest.mark.asyncio
async def test_fetch_list_mode_returns_games():
    dao = _StubDAO(games=[{"game_id": "G1"}, {"game_id": "G2"}])
    out = await do_fetch(dao, date="20260517", sport="S", game_id=None,
                         cheer_size=None, default_cheer_size=30)
    assert out == {
        "date": "20260517", "sport": "S",
        "games": [{"game_id": "G1"}, {"game_id": "G2"}],
    }
    assert dao.calls == [("get_games", "20260517", "S")]


@pytest.mark.asyncio
async def test_fetch_single_game_mode_returns_match_info_and_recent_cheers():
    dao = _StubDAO(bundle={
        "game": {"game_id": "G1", "home_team": "토트넘"},
        "cheers": [
            {"content": "가즈아", "team_name": "토트넘"},
            {"content": "토트넘 화이팅", "team_name": "토트넘"},
        ],
    })
    out = await do_fetch(dao, date="20260517", sport="S", game_id="G1",
                         cheer_size=5, default_cheer_size=30)
    assert out["date"] == "20260517"
    assert out["sport"] == "S"
    assert out["game_id"] == "G1"
    assert out["match_info"] == {"game_id": "G1", "home_team": "토트넘"}
    assert out["recent_cheers"] == [
        {"content": "가즈아", "team_name": "토트넘"},
        {"content": "토트넘 화이팅", "team_name": "토트넘"},
    ]
    # MSSQL 경로는 live_board/history 키 자체가 없음 → Jinja {% if %}가 블록 생략
    assert "live_board" not in out
    assert "history" not in out
    assert dao.calls == [("get_game_with_cheers", "20260517", "S", "G1", 5)]


@pytest.mark.asyncio
async def test_fetch_uses_default_cheer_size_when_none():
    dao = _StubDAO(bundle={"game": {"game_id": "G1"}, "cheers": []})
    await do_fetch(dao, date="20260517", sport="S", game_id="G1",
                   cheer_size=None, default_cheer_size=30)
    assert dao.calls[0] == ("get_game_with_cheers", "20260517", "S", "G1", 30)
