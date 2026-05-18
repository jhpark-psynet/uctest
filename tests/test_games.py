"""uctest games 단위 테스트.

DAO를 stub으로 갈아끼고 인자 흐름·출력 모양만 검증 (DB 접속 없음).
"""
from __future__ import annotations

import pytest

from uctest.games import do_games


class _StubDAO:
    def __init__(self, games=None):
        self._games = games or []
        self.calls: list[tuple] = []

    async def get_games(self, date, sport):
        self.calls.append(("get_games", date, sport))
        return self._games


@pytest.mark.asyncio
async def test_games_returns_list_with_meta():
    dao = _StubDAO(games=[
        {"game_id": "g1", "home": "Arsenal", "away": "Spurs"},
        {"game_id": "g2", "home": "Chelsea", "away": "City"},
    ])
    out = await do_games(dao, date="20260518", sport="S")
    assert out == {
        "date": "20260518",
        "sport": "S",
        "games": [
            {"game_id": "g1", "home": "Arsenal", "away": "Spurs"},
            {"game_id": "g2", "home": "Chelsea", "away": "City"},
        ],
    }
    assert dao.calls == [("get_games", "20260518", "S")]


@pytest.mark.asyncio
async def test_games_empty_list_when_no_matches():
    dao = _StubDAO(games=[])
    out = await do_games(dao, date="20260518", sport="B")
    assert out["games"] == []
    assert out["date"] == "20260518"
    assert out["sport"] == "B"


@pytest.mark.asyncio
async def test_games_empty_sport_passed_through():
    dao = _StubDAO(games=[{"game_id": "x"}])
    await do_games(dao, date="20260518", sport="")
    assert dao.calls == [("get_games", "20260518", "")]
