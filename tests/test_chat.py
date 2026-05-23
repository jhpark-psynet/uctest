"""uctest chat 단위 테스트.

_render_users·_wrap_results·_resolve_game_data·do_chat 흐름을 MockLLMProvider 주입으로 검증.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from uctest.chat import (
    _render_users,
    _resolve_game_data,
    _resolve_user_template,
    _wrap_results,
    do_chat,
)

from .conftest import MockLLMProvider


# --- _render_users ---


def test_render_users_question_per_iteration():
    out = _render_users(
        "Q={{ question }} HOME={{ game.home }}",
        ["Q1", "Q2"],
        {"game": {"home": "Arsenal"}},
    )
    assert out == ["Q=Q1 HOME=Arsenal", "Q=Q2 HOME=Arsenal"]


def test_render_users_uses_plain_json_filter():
    # prompt_builder._env 의 plain_json 필터(한글 escape 안 함)가 적용되는지
    out = _render_users(
        "{{ cheers | tojson }}",
        ["q"],
        {"cheers": ["응원해", "이겨라"]},
    )
    # default jinja tojson은 \uXXXX escape하지만 plain_json은 raw 한글
    assert "응원해" in out[0]
    assert "이겨라" in out[0]


def test_render_users_empty_cheers_renders_empty_list():
    out = _render_users("{{ cheers | length }}", ["q"], {"cheers": []})
    assert out == ["0"]


def test_render_users_aliases_legacy_game_and_cheers_to_match_info_and_recent_cheers():
    # 옛 fetch 출력(game/cheers) 또는 사용자가 손으로 만든 dict를 그대로 받아도
    # 새 user.jinja 슬롯(match_info/recent_cheers)으로 fallback 별칭이 걸린다.
    out = _render_users(
        "mi.home={{ match_info.home }} cheers0={{ recent_cheers[0] }}",
        ["q"],
        {"game": {"home": "Spurs"}, "cheers": ["go!"]},
    )
    assert out == ["mi.home=Spurs cheers0=go!"]


def test_render_users_aliases_legacy_data_key_to_match_info():
    # 더 옛 alias(data)도 같이 받아준다.
    out = _render_users(
        "{{ match_info.home }}",
        ["q"],
        {"data": {"home": "Tottenham"}},
    )
    assert out == ["Tottenham"]


def test_render_users_alias_does_not_override_explicit_keys():
    # game_data가 이미 match_info/recent_cheers를 명시했으면 그쪽이 우선.
    out = _render_users(
        "{{ match_info }}|{{ recent_cheers }}",
        ["q"],
        {"game": {"home": "X"}, "cheers": ["a"],
         "match_info": "EXPLICIT", "recent_cheers": ["EXPL"]},
    )
    assert out == ["EXPLICIT|['EXPL']"]


# --- _resolve_user_template ---


def _ns(**kw) -> SimpleNamespace:
    defaults = dict(
        system=None, system_file=None,
        user_template=None, user_template_file=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_resolve_user_template_text_arg():
    assert _resolve_user_template(_ns(user_template="hello")) == "hello"


def test_resolve_user_template_file(tmp_path):
    p = tmp_path / "tpl.jinja"
    p.write_text("Q={{question}}", encoding="utf-8")
    assert _resolve_user_template(_ns(user_template_file=str(p))) == "Q={{question}}"


def test_resolve_user_template_mutex_raises():
    with pytest.raises(ValueError, match="mutually exclusive"):
        _resolve_user_template(_ns(user_template="a", user_template_file="b"))


def test_resolve_user_template_missing_raises():
    with pytest.raises(ValueError, match="user template missing"):
        _resolve_user_template(_ns())


# --- _resolve_game_data ---


def test_resolve_game_data_loads_json(tmp_path):
    p = tmp_path / "g.json"
    p.write_text(json.dumps({"game": {"home": "X"}, "cheers": []}), encoding="utf-8")
    out = _resolve_game_data(str(p))
    assert out == {"game": {"home": "X"}, "cheers": []}


def test_resolve_game_data_rejects_list(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON/YAML object"):
        _resolve_game_data(str(p))


# --- _wrap_results ---


def _raw_results(items):
    return {
        "started_at": "2026-05-18T00:00:00+09:00",
        "duration_seconds": 0.123,
        "results": items,
    }


def test_wrap_results_maps_question_idx_to_question_text():
    raw = _raw_results([
        {"user_idx": 0, "user": "user-A", "provider": "gemini", "model": "g",
         "text": "ans1", "input_tokens": 1, "output_tokens": 2, "error": None},
        {"user_idx": 1, "user": "user-B", "provider": "openai", "model": "o",
         "text": "ans2", "input_tokens": 3, "output_tokens": 4, "error": None},
    ])
    wrapped = _wrap_results(raw, ["Q0", "Q1"], ["U0", "U1"], [["gemini", "g"]], False)
    assert wrapped["questions"] == ["Q0", "Q1"]
    assert wrapped["results"][0]["question"] == "Q0"
    assert wrapped["results"][1]["question"] == "Q1"
    assert "user_prompt" not in wrapped["results"][0]   # include_prompts=False
    assert "user" not in wrapped["results"][0]          # raw user 텍스트 노출 안 함


def test_wrap_results_include_prompts_adds_user_prompt():
    raw = _raw_results([
        {"user_idx": 0, "user": "U0", "provider": "g", "model": "m",
         "text": "x", "input_tokens": None, "output_tokens": None, "error": None},
    ])
    wrapped = _wrap_results(raw, ["Q0"], ["RENDERED-U0"], [["g", "m"]], True)
    assert wrapped["results"][0]["user_prompt"] == "RENDERED-U0"


def test_wrap_results_include_prompts_attaches_system_prompt():
    raw = _raw_results([])
    wrapped = _wrap_results(raw, [], [], [["g", "m"]], True, system="SYS-TEXT")
    assert wrapped["system_prompt"] == "SYS-TEXT"


def test_wrap_results_no_system_prompt_when_include_prompts_false():
    raw = _raw_results([])
    wrapped = _wrap_results(raw, [], [], [["g", "m"]], False, system="SYS-TEXT")
    assert "system_prompt" not in wrapped


def test_wrap_results_preserves_meta_and_models():
    raw = _raw_results([])
    wrapped = _wrap_results(raw, [], [], [["g", "m"]], False)
    assert wrapped["started_at"] == "2026-05-18T00:00:00+09:00"
    assert wrapped["duration_seconds"] == 0.123
    assert wrapped["models"] == [["g", "m"]]


# --- do_chat 전체 흐름 ---


def _factory_text(text: str):
    def _create(provider: str, api_key: str, model_name: str):
        return MockLLMProvider(
            f"{provider}:{model_name}:{text}",
            input_tokens=10, output_tokens=20,
        )
    return _create


@pytest.mark.asyncio
async def test_do_chat_full_matrix():
    out = await do_chat(
        system="sys",
        user_template="Q={{question}} GAME={{game.home}}",
        questions=["Q1", "Q2"],
        game_data={"game": {"home": "Arsenal"}},
        models=[["gemini", "g"], ["openai", "o"]],
        api_key_for=lambda p: "k",
        provider_factory=_factory_text("ok"),
    )
    # 2 questions × 2 models = 4 results
    assert len(out["results"]) == 4
    assert out["questions"] == ["Q1", "Q2"]
    # question 0은 Q1, 1은 Q2
    by_q = {r["question_idx"]: r["question"] for r in out["results"]}
    assert by_q[0] == "Q1" and by_q[1] == "Q2"
    # provider 매트릭스 모양 확인
    providers = sorted({r["provider"] for r in out["results"]})
    assert providers == ["gemini", "openai"]


@pytest.mark.asyncio
async def test_do_chat_include_prompts_attaches_rendered_user():
    out = await do_chat(
        system="sys",
        user_template="Q:{{question}}",
        questions=["hi"],
        game_data={},
        models=[["gemini", "g"]],
        api_key_for=lambda p: "k",
        provider_factory=_factory_text("ans"),
        include_prompts=True,
    )
    assert out["results"][0]["user_prompt"] == "Q:hi"
    assert out["system_prompt"] == "sys"


@pytest.mark.asyncio
async def test_do_chat_template_can_access_cheers_and_game():
    out = await do_chat(
        system="sys",
        user_template="HOME={{game.home}} N={{cheers|length}}",
        questions=["q"],
        game_data={"game": {"home": "Tottenham"}, "cheers": ["a", "b", "c"]},
        models=[["gemini", "g"]],
        api_key_for=lambda p: "k",
        provider_factory=_factory_text("x"),
        include_prompts=True,
    )
    assert out["results"][0]["user_prompt"] == "HOME=Tottenham N=3"
