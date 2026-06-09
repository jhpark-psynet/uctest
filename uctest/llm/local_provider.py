"""Local OpenAI-compatible LLM providers — vLLM / LM Studio / Ollama 등.

`OpenAIProvider`에 base_url만 다르게 꽂는 thin wrapper들. base_url은 config
settings에서 읽으므로 `.env` 한 줄로 동작한다(os.environ을 직접 읽던 기존
방식의 영속성 함정 제거 — pydantic-settings는 .env를 settings로만 읽고
os.environ에 export하지 않는다). 프로세스 전역 env var를 직접 export하면
그게 최우선(settings보다 명시적).

provider 토큰을 분리해 LM Studio(`lmstudio:`)와 vLLM(`vllm:`)을 한 매트릭스
에서 동시에 비교할 수 있다. 둘은 같은 OpenAI-compatible 어댑터지만 향하는
포트가 다르다. 런타임 식별이 필요하면:
  - LM Studio:  GET /api/v0/models → 200 (네이티브 REST)
  - vLLM:       GET /version       → {"version": "..."}
api_key는 보통 의미 없으므로 'EMPTY' default.
"""
from __future__ import annotations

import os

from uctest.config import settings
from .openai_provider import OpenAIProvider


def _resolve_base_url(settings_attr: str, env_var: str, default: str) -> str:
    """base_url 우선순위: 프로세스 env var > .env(settings) > 코드 default.

    env_var는 `VAR=... uctest ...` 식 inline export를 잡기 위함. settings도
    pydantic-settings가 os.environ을 보긴 하지만, 명시적 우선순위를 코드로
    드러내고 settings 싱글톤이 늦게 갱신되는 경우까지 커버한다.
    """
    return os.environ.get(env_var) or getattr(settings, settings_attr, "") or default


class LocalLLMProvider(OpenAIProvider):
    """범용 `local:` 토큰 — LOCAL_LLM_BASE_URL (기본 vLLM :8000). 하위호환 유지."""

    def __init__(self, api_key: str = "EMPTY", model_name: str = ""):
        base_url = _resolve_base_url(
            "local_llm_base_url", "LOCAL_LLM_BASE_URL", "http://localhost:8000/v1"
        )
        # api_key가 빈 문자열이면 OpenAI SDK가 거부할 수 있어 'EMPTY'로 보강
        super().__init__(api_key=api_key or "EMPTY", model_name=model_name, base_url=base_url)


class LMStudioProvider(OpenAIProvider):
    """`lmstudio:` 토큰 — LMSTUDIO_BASE_URL (기본 127.0.0.1:1234)."""

    def __init__(self, api_key: str = "EMPTY", model_name: str = ""):
        base_url = _resolve_base_url(
            "lmstudio_base_url", "LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"
        )
        super().__init__(api_key=api_key or "EMPTY", model_name=model_name, base_url=base_url)


class VLLMProvider(OpenAIProvider):
    """`vllm:` 토큰 — VLLM_BASE_URL (기본 localhost:8000)."""

    def __init__(self, api_key: str = "EMPTY", model_name: str = ""):
        base_url = _resolve_base_url(
            "vllm_base_url", "VLLM_BASE_URL", "http://localhost:8000/v1"
        )
        super().__init__(api_key=api_key or "EMPTY", model_name=model_name, base_url=base_url)
