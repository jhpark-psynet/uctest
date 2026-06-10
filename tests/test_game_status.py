"""게임리스트 state 코드 → status 매핑 단위 테스트.

확정 코드값(메모리 reference_data30_state_codes): B 경기전 / I 경기중 / F 종료 / C 취소.
순수 함수라 DB 접속 없음.
"""
from __future__ import annotations

from uctest.livescore.dao import _build_game_json, _convert_status


def _game(**over):
    """_build_game_json 호출용 최소 kwargs 채움 + 오버라이드."""
    base = dict(
        game_id="g1", compe="baseball", home_team="두산", away_team="삼성",
        home_score="3", away_score="1", state="I", state_txt="",
        match_date="20260610", match_time="18:30", league_name="KBO",
        today="20260610", home_team_id="OB", away_team_id="SS",
    )
    base.update(over)
    return _build_game_json(**base)


# --- _convert_status: 확정 코드 4종 ---

def test_convert_status_cancelled():
    assert _convert_status("C") == "CANCELLED"


def test_convert_status_pre_game():
    assert _convert_status("B") == "UPCOMING"


def test_convert_status_live():
    assert _convert_status("I") == "LIVE"


def test_convert_status_finished():
    assert _convert_status("F") == "FINISHED"


# --- _build_game_json: 취소 경기 출력 ---

def test_build_game_json_cancelled_status_and_label():
    g = _game(state="C", state_txt="")
    assert g["status"] == "CANCELLED"
    assert g["status_text"] == "취소"
