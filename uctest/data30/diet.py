"""baseball fetch 출력 입력 다이어트 — docs/input_diet.md §2-§3 처방.

LIVE 스코어 챗봇에서 DATA30 `match_info`를 통째로 LLM에 넣으면 쿼리당 입력이
~25k+ 토큰에 달하고, 대부분은 답변에 불필요한 raw 블록이다. 게다가 ① 이닝 누계
raw와 ② 투수 시즌/금일 누계 혼재가 **스코어 오독·투수 환각**을 유발한다.

`apply_diet`는 fetch 출력(do_fetch baseball 경로)을 받아:
- 제거: play_info(투구 시퀀스), vs(이닝 누계 — 스코어 오독원).
- 요약: player_info 투수(§3-② 라벨 분리)·타자(핵심 필드), betting(현재 배당), team_rank(해당 2팀).
- 추가: §3-① 현재 스코어 단일 진실원 필드(`_현재스코어_유일정답` + `_주의`)를 match_info **내부**에.

top-level 형태는 보존 — user.jinja가 `match_info`/`live_board`/`recent_cheers` 슬롯을
그대로 렌더한다(§4 운영 함정: 정규화 필드는 반드시 match_info 안에 있어야 출력됨).

검증: docs/input_diet.md (match_info 50k자 → 2.3k자, 21배 축소, 투수 환각 12→0).
"""
from __future__ import annotations

from typing import Any

# match_info에서 통째로 버리는 블록 (토큰 최대 소비원 + 오독 유발원)
_DROP_BLOCKS = ("play_info", "vs")

_PITCHER_CAUTION = (
    "이닝·실점·볼넷 누계는 시즌/금일 혼재로 신뢰 불가하여 제외. "
    "오늘 세부 기록(이닝·실점)은 제공되지 않음."
)
_SCORE_CAUTION = (
    "위 값이 현재 점수의 유일한 출처다. 이닝별 누계는 제공하지 않으니 "
    "반드시 이 값만 사용하고, 응원글에서 점수를 추측하지 말 것."
)


def _first(obj: Any) -> dict[str, Any]:
    """list면 첫 원소, dict면 그대로, 그 외 빈 dict."""
    if isinstance(obj, list):
        return obj[0] if obj and isinstance(obj[0], dict) else {}
    return obj if isinstance(obj, dict) else {}


def _diet_pitcher(p: Any) -> dict[str, Any]:
    p = _first(p)
    return {
        "선수명": p.get("player_name"),
        "시즌ERA": p.get("earned_run_average"),
        "시즌승패": f'{p.get("win_count", "?")}승 {p.get("loss_count", "?")}패',
        "오늘_투구수": p.get("pitch_count"),
        "주의": _PITCHER_CAUTION,
    }


def _diet_hitter(h: dict[str, Any]) -> dict[str, Any]:
    return {
        "타순": h.get("bat_order_no"),
        "선수명": h.get("player_name"),
        "시즌타율": h.get("batting_average"),
        "오늘_타수": h.get("at_bat_count"),
        "오늘_안타": h.get("hit_count"),
    }


def _diet_betting(betting: Any) -> dict[str, Any]:
    rows = betting if isinstance(betting, list) else []
    cur = rows[0] if rows and isinstance(rows[0], dict) else {}
    return {
        "홈배당": cur.get("home_bet_rate"),
        "원정배당": cur.get("away_bet_rate"),
        "핸디캡": cur.get("handicap_score"),
        "언더오버기준": cur.get("under_over_score") or "(제공 안 됨)",
        "_주의": "언더오버 기준점이 비어 있으면 제공되지 않은 것 — 추측 금지.",
    }


def _diet_team_rank(team_rank: Any, home_id: str, away_id: str,
                    home: str, away: str) -> list[dict[str, Any]]:
    rows = team_rank if isinstance(team_rank, list) else (
        list(team_rank.values()) if isinstance(team_rank, dict) else [])
    out: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get("team_id") in (home_id, away_id) or r.get("team_name") in (home, away):
            out.append({
                "팀": r.get("team_name"),
                "승": r.get("win_count"),
                "패": r.get("loss_count"),
                "게임차": r.get("games_back"),
                "시즌득점": r.get("runs_scored"),
            })
    return out


# live_board에서 남길 라이브 상황 핵심 필드
_LIVE_KEEP = (
    "pitch_count", "runner_status", "away_team_hits", "home_team_hits",
    "batter_ab_count", "batter_hit_count", "b1_player_name",
)


def diet_match_info(match_info: dict[str, Any]) -> dict[str, Any]:
    """match_info 단독 다이어트. game_info 기반으로 §3-① 스코어 진실원 추가."""
    gi = match_info.get("game_info") or {}
    home = gi.get("home_team_name", "")
    away = gi.get("away_team_name", "")
    home_id = gi.get("home_team_id", "")
    away_id = gi.get("away_team_id", "")
    hs = gi.get("home_score", "")
    as_ = gi.get("away_score", "")
    inning = gi.get("game_state_detail_text", "")

    pi = match_info.get("player_info") or {}
    players = {
        f"{away}_선발투수": _diet_pitcher(pi.get("away_pitcher")),
        f"{home}_선발투수": _diet_pitcher(pi.get("home_pitcher")),
        f"{away}_타자": [_diet_hitter(h) for h in (pi.get("away_hitter") or []) if isinstance(h, dict)],
        f"{home}_타자": [_diet_hitter(h) for h in (pi.get("home_hitter") or []) if isinstance(h, dict)],
    }

    return {
        "game_info": {
            "home_team_name": home,
            "away_team_name": away,
            "league_name": gi.get("league_name"),
            "상태": gi.get("game_state_text"),
        },
        "_현재스코어_유일정답": f"{home} {hs} : {as_} {away} ({inning})",
        "_주의": _SCORE_CAUTION,
        "betting_info": _diet_betting(match_info.get("betting_info")),
        "player_info": players,
        "team_rank": _diet_team_rank(match_info.get("team_rank"), home_id, away_id, home, away),
    }


def apply_diet(fetched: dict[str, Any]) -> dict[str, Any]:
    """fetch 출력(baseball) → 다이어트 출력. top-level 슬롯 형태 보존.

    match_info가 없으면(다른 스포츠/스키마) 원본을 그대로 반환한다.
    """
    mi = fetched.get("match_info")
    if not isinstance(mi, dict) or "game_info" not in mi:
        return fetched

    out = dict(fetched)
    out["match_info"] = diet_match_info(mi)

    lb = fetched.get("live_board")
    if isinstance(lb, dict):
        out["live_board"] = {k: lb[k] for k in _LIVE_KEEP if lb.get(k) is not None}
    return out
