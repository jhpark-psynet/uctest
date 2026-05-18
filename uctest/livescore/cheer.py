"""livescore 응원글 추출 헬퍼.

unifiedchat 본체에서는 livescore/endpoints.py(FastAPI 라우터) 내부 함수였지만,
uctest는 라우터를 들고 갈 필요가 없어 함수만 별도 모듈로 떼어둔다.
"""
from __future__ import annotations

from typing import Any


def _extract_cheer_contents(cheers: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for c in cheers:
        content = c.get("content")
        if isinstance(content, str) and content.strip():
            out.append(content)
    return out
