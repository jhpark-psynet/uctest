from __future__ import annotations

from typing import Any


_CHEER_AI_FIELDS = ("ai_content", "ai_type", "ai_name")


def _unwrap_list(section: Any) -> list[Any]:
    """DATA30의 top-level list-valued 섹션은 `{list: [...]}` 형태로 wrap돼 있다.

    이미 list거나 dict({list}) 둘 다 받아서 inner list만 반환. 누락/타입오류면 빈 list.
    """
    if isinstance(section, list):
        return section
    if isinstance(section, dict):
        inner = section.get("list")
        if isinstance(inner, list):
            return inner
    return []


def to_match_info(raw: dict[str, Any]) -> dict[str, Any]:
    """live_board / cheer / my_cheer 를 제외한 나머지를 묶어서 LLM 컨텍스트로 노출."""
    return {
        "game_info": raw.get("game_info") or {},
        "team_rank": _unwrap_list(raw.get("team_rank")),
        "play_info": _unwrap_list(raw.get("play_info")),
        "vs": raw.get("vs") or {},
        "player_info": raw.get("player_info") or {},
        "betting_info": _unwrap_list(raw.get("betting_info")),
    }


def to_live_board(raw: dict[str, Any]) -> Any:
    """live_board.list[0] 만 펴서 single dict로 정규화."""
    rows = _unwrap_list(raw.get("live_board"))
    if rows and isinstance(rows[0], dict):
        return rows[0]
    return None


def to_recent_cheers(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """cheer.list 중 사람 응원글(content 있는 행)만, ai_* 필드 제거."""
    out: list[dict[str, Any]] = []
    for row in _unwrap_list(raw.get("cheer")):
        if not isinstance(row, dict):
            continue
        content = row.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        out.append({k: v for k, v in row.items() if k not in _CHEER_AI_FIELDS})
    return out


def to_history(raw: dict[str, Any]) -> list[dict[str, str]]:
    """my_cheer.list 각 row → [{role:user, content}, {role:assistant, content:ai_content}, ...].

    응답에 my_cheer가 없을 수도 있다 (인증 없는 호출). 그때는 빈 리스트.
    """
    out: list[dict[str, str]] = []
    for row in _unwrap_list(raw.get("my_cheer")):
        if not isinstance(row, dict):
            continue
        content = row.get("content")
        if isinstance(content, str) and content.strip():
            out.append({"role": "user", "content": content})
        ai = row.get("ai_content")
        if isinstance(ai, str) and ai.strip():
            out.append({"role": "assistant", "content": ai})
    return out
