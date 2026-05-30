from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class Data30Client:
    def __init__(
        self,
        *,
        base_url: str,
        auth_key: str,
        timeout: float = 15.0,
    ):
        if not base_url:
            raise ValueError("DATA30_BASE_URL is required")
        if not auth_key:
            raise ValueError("DATA30_AUTH_KEY is required")
        self._base_url = base_url.rstrip("/")
        self._auth_key = auth_key
        self._timeout = timeout

    async def get_baseball_total_question(self, game_id: str) -> dict[str, Any]:
        url = f"{self._base_url}/livescore/baseballTotalQuestion"
        params = {"auth_key": self._auth_key, "game_id": game_id}
        async with httpx.AsyncClient(timeout=self._timeout) as cx:
            r = await cx.get(url, params=params)
            r.raise_for_status()
            payload = r.json()
        if not isinstance(payload, dict):
            logger.error("data30.bad_payload", url=url, game_id=game_id)
            return {}
        # 실제 응답: {Data: {list: {game_info, live_board, cheer, ...}}, lastUpdated}
        # 명세상 Data 직속 키처럼 적혀 있지만 실제로는 한 단계 더 wrap돼 있음.
        data = payload.get("Data") or payload.get("data") or {}
        if not isinstance(data, dict):
            logger.error("data30.bad_data_key", url=url, game_id=game_id)
            return {}
        inner = data.get("list")
        return inner if isinstance(inner, dict) else data
