"""입력 다이어트(uctest.data30.diet) 테스트.

docs/input_diet.md §2-§3 처방: 노이즈 블록 제거, 스코어 단일 진실원,
투수 시즌/금일 라벨 분리, 비-baseball 통과를 검증한다.
"""
from __future__ import annotations

import json

from uctest.data30.diet import apply_diet, diet_match_info

_SAMPLE_MI = {
    "game_info": {
        "home_team_name": "애슬레틱스", "away_team_name": "밀워키",
        "home_team_id": "OT1235", "away_team_id": "OT1232",
        "home_score": "10", "away_score": "8",
        "league_name": "MLB", "game_state_text": "경기중",
        "game_state_detail_text": "9회초",
    },
    "betting_info": [
        {"home_bet_rate": "2.26", "away_bet_rate": "1.44", "handicap_score": "0.0",
         "under_over_score": "", "before_home_bet_rate": "2.37"},
        {"home_bet_rate": "2.37", "away_bet_rate": "1.40"},
    ],
    "player_info": {
        "away_pitcher": [{"player_name": "해리슨", "earned_run_average": "1.57",
                          "win_count": "7", "loss_count": "1", "pitch_count": "71",
                          "innings_pitched": "7", "walk_count": "16", "earned_runs": "8"}],
        "home_pitcher": [{"player_name": "스프링스", "earned_run_average": "4.37",
                          "win_count": "3", "loss_count": "2", "pitch_count": "99"}],
        "away_hitter": [{"bat_order_no": "1", "player_name": "옐리치",
                         "batting_average": ".282", "at_bat_count": "5", "hit_count": "1",
                         "slugging_percentage": ".443", "player_id": "X"}],
        "home_hitter": [{"bat_order_no": "3", "player_name": "타티스",
                         "batting_average": ".301", "at_bat_count": "4", "hit_count": "2"}],
    },
    "team_rank": [
        {"team_id": "OT1232", "team_name": "밀워키", "win_count": "40", "loss_count": "28",
         "games_back": "-", "runs_scored": "355"},
        {"team_id": "OT9999", "team_name": "클리블랜드", "win_count": "37", "loss_count": "31"},
        {"team_id": "OT1235", "team_name": "애슬레틱스", "win_count": "30", "loss_count": "38",
         "games_back": "10.0", "runs_scored": "314"},
    ],
    "play_info": [{"x": "투구 시퀀스 " * 50}],   # 노이즈 — 제거 대상
    "vs": {"inning_info": [{"i": 1}], "scoreboard_record": "3:0"},  # 이닝 누계 — 제거 대상
}


def test_drops_noise_blocks():
    d = diet_match_info(_SAMPLE_MI)
    assert "play_info" not in d
    assert "vs" not in d


def test_single_source_score_field():
    d = diet_match_info(_SAMPLE_MI)
    assert d["_현재스코어_유일정답"] == "애슬레틱스 10 : 8 밀워키 (9회초)"
    assert "_주의" in d and "유일한 출처" in d["_주의"]


def test_pitcher_label_separation():
    d = diet_match_info(_SAMPLE_MI)
    p = d["player_info"]["밀워키_선발투수"]
    assert p["선수명"] == "해리슨"
    assert p["시즌ERA"] == "1.57"
    assert p["오늘_투구수"] == "71"
    # 시즌/금일 혼재 필드(이닝·실점·볼넷 누계)는 빠지고 주의 라벨이 붙는다
    assert "innings_pitched" not in p
    assert "walk_count" not in p
    assert "주의" in p


def test_hitter_trimmed_to_core():
    d = diet_match_info(_SAMPLE_MI)
    h = d["player_info"]["밀워키_타자"][0]
    assert h == {"타순": "1", "선수명": "옐리치", "시즌타율": ".282",
                 "오늘_타수": "5", "오늘_안타": "1"}
    assert "slugging_percentage" not in h and "player_id" not in h


def test_betting_current_only():
    d = diet_match_info(_SAMPLE_MI)
    b = d["betting_info"]
    assert b["홈배당"] == "2.26" and b["원정배당"] == "1.44"
    assert b["언더오버기준"] == "(제공 안 됨)"   # 빈 값 → 명시


def test_team_rank_only_two_teams():
    d = diet_match_info(_SAMPLE_MI)
    names = {r["팀"] for r in d["team_rank"]}
    assert names == {"밀워키", "애슬레틱스"}   # 클리블랜드 제외


def test_apply_diet_preserves_toplevel_and_shrinks():
    fetched = {
        "date": "20260609", "sport": "B", "game_id": "G1",
        "match_info": _SAMPLE_MI,
        "live_board": {"pitch_count": "8", "away_team_hits": "13", "season_era": "2.40"},
        "recent_cheers": [{"content": "가자"}],
        "history": [],
    }
    out = apply_diet(fetched)
    # top-level 슬롯 보존
    assert out["recent_cheers"] == [{"content": "가자"}]
    assert out["game_id"] == "G1"
    # live_board는 핵심 필드만
    assert "season_era" not in out["live_board"]
    assert out["live_board"]["pitch_count"] == "8"
    # 실제로 작아졌는지
    assert len(json.dumps(out["match_info"], ensure_ascii=False)) < \
           len(json.dumps(_SAMPLE_MI, ensure_ascii=False))


def test_non_baseball_passthrough():
    fetched = {"sport": "S", "match_info": {"home_team": "A", "away_team": "B"}}
    assert apply_diet(fetched) is fetched   # game_info 없음 → 원본 그대로
