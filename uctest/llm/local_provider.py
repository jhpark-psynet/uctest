"""Local OpenAI-compatible LLM provider — vLLM / Ollama / LM Studio 등.

`OpenAIProvider`에 base_url만 다르게 꽂는 thin wrapper. base_url은 환경변수
`LOCAL_LLM_BASE_URL`로 조정 (기본 http://localhost:8000/v1, vLLM 기본 포트).
api_key는 보통 의미 없으므로 'EMPTY' default.
"""
from __future__ import annotations

import os

from .openai_provider import OpenAIProvider


class LocalLLMProvider(OpenAIProvider):
    def __init__(self, api_key: str = "EMPTY", model_name: str = ""):
        base_url = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:8000/v1")
        # api_key가 빈 문자열이면 OpenAI SDK가 거부할 수 있어 'EMPTY'로 보강
        super().__init__(api_key=api_key or "EMPTY", model_name=model_name, base_url=base_url)
