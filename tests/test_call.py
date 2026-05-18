"""uctest call 단위 테스트.

users × models 매트릭스 카디널리티, 결과 모양, 일부 실패 처리를 검증한다.
MockLLMProvider를 factory 자리에 주입해 실제 LLM 호출은 일어나지 않게 한다.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from .conftest import MockLLMProvider
from uctest.call import _resolve_system, _resolve_users, do_call


def _ns(**kw) -> SimpleNamespace:
    defaults = dict(system=None, system_file=None, user=[], user_file=[])
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _factory_text(text: str):
    def _create(provider: str, api_key: str, model_name: str):
        return MockLLMProvider(f"{provider}:{model_name}:{text}",
                                input_tokens=10, output_tokens=20)
    return _create


@pytest.mark.asyncio
async def test_do_call_full_matrix_cardinality():
    out = await do_call(
        system="sys",
        users=["q1", "q2", "q3"],
        models=[("gemini", "g-flash"), ("openai", "gpt-nano")],
        provider_factory=_factory_text("ok"),
        api_key_for=lambda p: "fake",
    )
    assert len(out["results"]) == 6        # 3 users × 2 models
    # 각 user_idx별 results 개수 == models 수
    by_user: dict[int, list[dict]] = {}
    for r in out["results"]:
        by_user.setdefault(r["user_idx"], []).append(r)
    assert sorted(by_user.keys()) == [0, 1, 2]
    assert all(len(v) == 2 for v in by_user.values())


@pytest.mark.asyncio
async def test_do_call_result_fields_populated():
    out = await do_call(
        system="sys",
        users=["hello"],
        models=[("gemini", "g-flash")],
        provider_factory=_factory_text("answer"),
        api_key_for=lambda p: "fake",
    )
    r = out["results"][0]
    assert r["user_idx"] == 0
    assert r["user"] == "hello"
    assert r["provider"] == "gemini"
    assert r["model"] == "g-flash"
    assert r["text"] == "gemini:g-flash:answer"
    assert r["input_tokens"] == 10
    assert r["output_tokens"] == 20
    assert r["error"] is None


class _ExplodingProvider:
    def __init__(self, **kwargs):
        pass

    async def generate(self, system, user, config=None):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_do_call_individual_failure_isolated():
    def _factory(provider, key, model):
        if provider == "broken":
            return _ExplodingProvider()
        return MockLLMProvider("ok", input_tokens=1, output_tokens=2)

    out = await do_call(
        system="sys",
        users=["q1"],
        models=[("openai", "good"), ("broken", "bad")],
        provider_factory=_factory,
        api_key_for=lambda p: "fake",
    )
    by_provider = {r["provider"]: r for r in out["results"]}
    assert by_provider["openai"]["error"] is None
    assert by_provider["openai"]["text"] == "ok"
    assert by_provider["broken"]["error"] == "boom"
    assert by_provider["broken"]["text"] == ""


@pytest.mark.asyncio
async def test_do_call_meta_keys_present():
    out = await do_call(
        system="sys", users=["q"],
        models=[("openai", "gpt-nano")],
        provider_factory=_factory_text("x"),
        api_key_for=lambda p: "fake",
    )
    assert "started_at" in out
    assert "duration_seconds" in out
    assert isinstance(out["duration_seconds"], float)


# --- CLI 인자 해석기 (--system / --user / --user-file) ---


def test_resolve_system_arg_wins_over_payload():
    assert _resolve_system(_ns(system="arg-sys"), {"system": "yaml-sys"}) == "arg-sys"


def test_resolve_system_file_loaded(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text("from-file", encoding="utf-8")
    assert _resolve_system(_ns(system_file=str(p)), {}) == "from-file"


def test_resolve_system_mutex_raises():
    with pytest.raises(ValueError, match="mutually exclusive"):
        _resolve_system(_ns(system="x", system_file="/tmp/y"), {})


def test_resolve_system_falls_back_to_payload():
    assert _resolve_system(_ns(), {"system": "yaml-sys"}) == "yaml-sys"


def test_resolve_users_arg_wins_over_payload():
    out = _resolve_users(_ns(user=["a", "b"]), {"users": ["yaml-u"]})
    assert out == ["a", "b"]


def test_resolve_users_combines_text_and_file(tmp_path):
    f = tmp_path / "u.txt"
    f.write_text("from-file", encoding="utf-8")
    out = _resolve_users(_ns(user=["inline"], user_file=[str(f)]), {})
    assert out == ["inline", "from-file"]


def test_resolve_users_falls_back_to_payload():
    out = _resolve_users(_ns(), {"users": ["yaml-u1", "yaml-u2"]})
    assert out == ["yaml-u1", "yaml-u2"]


def test_resolve_users_payload_type_error():
    with pytest.raises(ValueError, match="must be a list"):
        _resolve_users(_ns(), {"users": "not-a-list"})
