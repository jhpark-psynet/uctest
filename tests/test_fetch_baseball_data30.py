"""uctest fetch — baseball + DATA30 경로 단위 테스트.

Data30Client을 stub으로 갈아끼고 출력 키/매핑/필터를 검증 (HTTP 호출 없음).
"""
from __future__ import annotations

import pytest

from uctest.data30 import baseball as data30_baseball
from uctest.fetch import do_fetch


class _StubData30Client:
    def __init__(self, raw):
        self._raw = raw
        self.calls: list[tuple] = []

    async def get_baseball_total_question(self, game_id: str):
        self.calls.append(("get_baseball_total_question", game_id))
        return self._raw


def _sample_raw() -> dict:
    """실제 DATA30 응답 shape (Data30Client가 Data.list까지 unwrap한 결과 기준).

    실측: top-level list-valued 섹션 (team_rank, play_info, live_board, cheer,
    betting_info, my_cheer)은 모두 `{list: [...]}` 형태로 한 단계 wrap돼 있다.
    game_info / vs / player_info 는 dict 직속.
    """
    return {
        "game_info": {
            "home_team_name": "두산",
            "away_team_name": "LG",
            "home_score": "3",
            "away_score": "2",
            "state": "I",
        },
        "team_rank": {"list": [
            {"team_name": "두산", "rank": "1"},
            {"team_name": "LG", "rank": "3"},
        ]},
        "live_board": {"list": [{
            "out_count": "1", "ball_count": "2", "strike_count": "1",
            "runner_status": "010", "home_team_hits": "5", "away_team_hits": "4",
        }]},
        "play_info": {"list": [
            {"inning_info": "5회초", "livetext_value_kr": "삼진!"},
        ]},
        "vs": {"inning_info": [], "team_vs_history": []},
        "player_info": {
            "home_hitter": [], "away_hitter": [],
            "home_pitcher": [], "away_pitcher": [],
        },
        "cheer": {"list": [
            {"content": "두산 가즈아!", "team_name": "두산", "ai_content": ""},
            {"content": "이번 회 역전", "team_name": "LG",
             "ai_content": "지금 분위기 좋네요", "ai_type": "1", "ai_name": "DSU"},
            {"content": "", "team_name": "LG",
             "ai_content": "순수 AI 응원글"},   # content 비어있으면 recent_cheers에서 제외
            {"content": None, "team_name": "두산"},  # None도 제외
        ]},
        "my_cheer": {"list": [
            {"content": "우리팀 어때?", "ai_content": "지금 3대 2 리드에요"},
            {"content": "이번 회 몇 득점?", "ai_content": ""},   # AI 답변 없으면 assistant turn 생략
            {"content": "", "ai_content": "사용자 응원글 없는 행"},   # user turn 생략
        ]},
        "betting_info": {"list": [{"game_type_code": "P", "home_bet_rate": "1.8"}]},
    }


# --- 매퍼 단위 ---


def test_to_match_info_bundles_non_live_board_non_cheer_fields():
    mi = data30_baseball.to_match_info(_sample_raw())
    assert mi["game_info"]["home_team_name"] == "두산"
    assert mi["team_rank"][0]["team_name"] == "두산"
    assert mi["play_info"][0]["inning_info"] == "5회초"
    assert "player_info" in mi
    assert "betting_info" in mi
    # live_board / cheer / my_cheer 는 들어가지 않는다
    assert "live_board" not in mi
    assert "cheer" not in mi
    assert "my_cheer" not in mi


def test_to_live_board_unwraps_single_item_list():
    lb = data30_baseball.to_live_board(_sample_raw())
    assert isinstance(lb, dict)
    assert lb["out_count"] == "1"
    assert lb["runner_status"] == "010"


def test_to_live_board_returns_none_when_missing():
    assert data30_baseball.to_live_board({}) is None
    assert data30_baseball.to_live_board({"live_board": []}) is None


def test_to_recent_cheers_filters_ai_only_rows_and_strips_ai_fields():
    cheers = data30_baseball.to_recent_cheers(_sample_raw())
    # 사람 응원 2개만 (AI-only 행, content None 행 제외)
    assert len(cheers) == 2
    contents = [c["content"] for c in cheers]
    assert contents == ["두산 가즈아!", "이번 회 역전"]
    # ai_* 필드는 모두 제거
    for c in cheers:
        assert "ai_content" not in c
        assert "ai_type" not in c
        assert "ai_name" not in c
    # team_name 같은 메타는 유지
    assert cheers[0]["team_name"] == "두산"


def test_to_history_pairs_user_and_assistant_turns():
    hist = data30_baseball.to_history(_sample_raw())
    # row 1: user + assistant (둘 다)
    # row 2: user만 (ai_content 비어있음)
    # row 3: assistant만 (content 비어있음)
    assert hist == [
        {"role": "user", "content": "우리팀 어때?"},
        {"role": "assistant", "content": "지금 3대 2 리드에요"},
        {"role": "user", "content": "이번 회 몇 득점?"},
        {"role": "assistant", "content": "사용자 응원글 없는 행"},
    ]


# --- do_fetch 통합 (DATA30 경로) ---


@pytest.mark.asyncio
async def test_fetch_baseball_uses_data30_client_and_returns_slot_keys():
    client = _StubData30Client(_sample_raw())
    out = await do_fetch(
        None,
        date="20260521",
        sport="B",
        game_id="BB-1",
        cheer_size=None,
        default_cheer_size=30,
        data30=client,
    )
    assert out["date"] == "20260521"
    assert out["sport"] == "B"
    assert out["game_id"] == "BB-1"
    assert "match_info" in out and "game_info" in out["match_info"]
    assert "live_board" in out and out["live_board"]["out_count"] == "1"
    assert len(out["recent_cheers"]) == 2
    assert len(out["history"]) == 4
    assert client.calls == [("get_baseball_total_question", "BB-1")]


@pytest.mark.asyncio
async def test_fetch_baseball_lowercase_sport_also_routes_to_data30():
    client = _StubData30Client(_sample_raw())
    out = await do_fetch(
        None,
        date="20260521",
        sport="b",          # 소문자도 baseball로 인식
        game_id="BB-2",
        cheer_size=None,
        default_cheer_size=30,
        data30=client,
    )
    assert out["match_info"]["game_info"]["home_team_name"] == "두산"
    assert client.calls == [("get_baseball_total_question", "BB-2")]


@pytest.mark.asyncio
async def test_fetch_baseball_falls_back_to_mssql_when_no_data30_provided():
    # data30=None 이면 baseball이라도 MSSQL 경로로 떨어진다 (DAO 필요).
    class _DAO:
        async def get_game_with_cheers(self, *a, **kw):
            return {"game": {"game_id": "BB-3"}, "cheers": []}

    out = await do_fetch(
        _DAO(),
        date="20260521",
        sport="B",
        game_id="BB-3",
        cheer_size=None,
        default_cheer_size=30,
    )
    # MSSQL shape — live_board / history 키 없음
    assert out["match_info"] == {"game_id": "BB-3"}
    assert out["recent_cheers"] == []
    assert "live_board" not in out
    assert "history" not in out
