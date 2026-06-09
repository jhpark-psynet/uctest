"""로컬 OpenAI-compatible provider 라우팅·base_url 해석 테스트.

`lmstudio:` / `vllm:` / `local:` 토큰이 팩토리에 등록돼 있고, 각자 올바른
base_url(env > .env(settings) > default 우선순위)로 OpenAI 클라이언트를 꽂는지
검증한다. 실제 네트워크 호출은 하지 않는다 — 생성된 client.base_url만 본다.
"""
from __future__ import annotations

import pytest

from uctest.llm.factory import LLMProviderFactory
from uctest.llm.local_provider import (
    LMStudioProvider,
    LocalLLMProvider,
    VLLMProvider,
)


def _base_url(provider) -> str:
    # AsyncOpenAI는 base_url을 trailing slash 붙은 URL 객체로 보관
    return str(provider.client.base_url)


def test_factory_registers_local_tokens():
    for token, cls in [
        ("local", LocalLLMProvider),
        ("lmstudio", LMStudioProvider),
        ("vllm", VLLMProvider),
    ]:
        assert LLMProviderFactory.PROVIDERS[token] is cls


def test_lmstudio_default_port_1234(monkeypatch):
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)
    monkeypatch.setattr("uctest.llm.local_provider.settings.lmstudio_base_url", "")
    assert "127.0.0.1:1234" in _base_url(LMStudioProvider(model_name="m"))


def test_vllm_default_port_8000(monkeypatch):
    monkeypatch.delenv("VLLM_BASE_URL", raising=False)
    monkeypatch.setattr("uctest.llm.local_provider.settings.vllm_base_url", "")
    assert "8000" in _base_url(VLLMProvider(model_name="m"))


def test_env_var_overrides_settings(monkeypatch):
    monkeypatch.setattr("uctest.llm.local_provider.settings.lmstudio_base_url",
                        "http://from-settings:1/v1")
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://from-env:9/v1")
    assert "from-env:9" in _base_url(LMStudioProvider(model_name="m"))


def test_settings_used_when_no_env(monkeypatch):
    monkeypatch.delenv("VLLM_BASE_URL", raising=False)
    monkeypatch.setattr("uctest.llm.local_provider.settings.vllm_base_url",
                        "http://dot-env-host:7/v1")
    assert "dot-env-host:7" in _base_url(VLLMProvider(model_name="m"))


def test_lmstudio_and_vllm_distinct_endpoints(monkeypatch):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://lms:1234/v1")
    monkeypatch.setenv("VLLM_BASE_URL", "http://vllm:8000/v1")
    assert _base_url(LMStudioProvider(model_name="m")) != _base_url(VLLMProvider(model_name="m"))


def test_created_via_factory(monkeypatch):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://lms:1234/v1")
    prov = LLMProviderFactory.create("lmstudio", api_key="", model_name="google/gemma-4-12b")
    assert isinstance(prov, LMStudioProvider)
    assert "lms:1234" in _base_url(prov)
    assert prov.model_name == "google/gemma-4-12b"
