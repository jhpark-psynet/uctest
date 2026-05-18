"""uctest fetch 단위 테스트.

LiveScoreDAO를 stub으로 갈아끼고 인자 흐름·출력 모양만 검증한다 (DB 접속 없음).
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
async def test_fetch_single_game_mode_returns_game_and_cheers():
    dao = _StubDAO(bundle={
        "game": {"game_id": "G1", "home_team": "토트넘"},
        "cheers": [
            {"content": "가즈아"},
            {"content": "토트넘 화이팅"},
            {"content": None},        # None은 제거
            {"content": "  "},        # 공백은 제거
            {"no_content": "..."},    # content 키 없으면 제거
        ],
    })
    out = await do_fetch(dao, date="20260517", sport="S", game_id="G1",
                         cheer_size=5, default_cheer_size=30)
    assert out["date"] == "20260517"
    assert out["sport"] == "S"
    assert out["game"] == {"game_id": "G1", "home_team": "토트넘"}
    assert out["cheers"] == ["가즈아", "토트넘 화이팅"]
    assert dao.calls == [("get_game_with_cheers", "20260517", "S", "G1", 5)]


@pytest.mark.asyncio
async def test_fetch_uses_default_cheer_size_when_none():
    dao = _StubDAO(bundle={"game": {"game_id": "G1"}, "cheers": []})
    await do_fetch(dao, date="20260517", sport="S", game_id="G1",
                   cheer_size=None, default_cheer_size=30)
    assert dao.calls[0] == ("get_game_with_cheers", "20260517", "S", "G1", 30)
