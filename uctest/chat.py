"""uctest chat — system + user 템플릿 + 질문 N개 + 데이터 1세트 + 모델 M개 매트릭스.

같은 (game, cheers) 데이터를 모든 질문에 공유한 채로 user 프롬프트 N개를 렌더한 뒤,
`call.do_call`로 users × models 매트릭스를 비동기 호출한다.

fetch 결과(`{date, sport, game, cheers}`)를 셸 파이프나 파일 인자로 받는 흐름을 가정.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from jinja2 import TemplateSyntaxError, UndefinedError

from uctest.call import (
    _parse_model_flag,
    _resolve_system,
    _settings_api_key_for,
    do_call,
)
from uctest.config import UnifiedChatSettings
from uctest.io import read_input, write_output
from uctest.llm.provider import LLMConfig
from uctest.prompt_builder import _env as _jinja_env


def _resolve_user_template(args: argparse.Namespace) -> str:
    if args.user_template is not None and args.user_template_file is not None:
        raise ValueError("--user-template and --user-template-file are mutually exclusive")
    if args.user_template is not None:
        return args.user_template
    if args.user_template_file is not None:
        return Path(args.user_template_file).read_text(encoding="utf-8")
    raise ValueError("user template missing (provide --user-template or --user-template-file)")


def _resolve_game_data(path_arg: str) -> dict[str, Any]:
    payload = read_input(path_arg)
    if not isinstance(payload, dict):
        raise ValueError("game-data must be a JSON/YAML object (got list or scalar)")
    return payload


def _render_users(
    user_template: str,
    questions: list[str],
    game_data: dict[str, Any],
) -> list[str]:
    tpl = _jinja_env.from_string(user_template)
    # fetch 출력 키(`game`/`cheers`)를 기본 user.jinja가 기대하는 슬롯 이름
    # (`data`/`recent_cheers`)으로 별칭 노출. 원본 키도 같이 두어 raw 접근
    # (`{{ game.home }}` 등)을 쓰는 커스텀 템플릿도 깨지지 않게 함.
    base = dict(game_data)
    if "data" not in base and "game" in game_data:
        base["data"] = game_data["game"]
    if "recent_cheers" not in base and "cheers" in game_data:
        base["recent_cheers"] = game_data["cheers"]
    out: list[str] = []
    for q in questions:
        ctx = {**base, "question": q}
        out.append(tpl.render(**ctx))
    return out


def _wrap_results(
    raw: dict[str, Any],
    questions: list[str],
    rendered_users: list[str],
    models: list[list[str]],
    include_prompts: bool,
    system: str | None = None,
) -> dict[str, Any]:
    wrapped_results: list[dict[str, Any]] = []
    for r in raw["results"]:
        idx = r["user_idx"]
        item: dict[str, Any] = {
            "question_idx": idx,
            "question": questions[idx],
            "provider": r["provider"],
            "model": r["model"],
            "text": r["text"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "error": r["error"],
        }
        if include_prompts:
            item["user_prompt"] = rendered_users[idx]
        wrapped_results.append(item)
    out: dict[str, Any] = {
        "started_at": raw["started_at"],
        "duration_seconds": raw["duration_seconds"],
        "questions": questions,
        "models": [list(m) for m in models],
        "results": wrapped_results,
    }
    if include_prompts and system is not None:
        out["system_prompt"] = system
    return out


async def do_chat(
    *,
    system: str,
    user_template: str,
    questions: list[str],
    game_data: dict[str, Any],
    models: list[list[str]],
    config: LLMConfig | None = None,
    api_key_for=None,
    include_prompts: bool = False,
    provider_factory=None,
) -> dict[str, Any]:
    rendered_users = _render_users(user_template, questions, game_data)
    call_kwargs = {
        "system": system,
        "users": rendered_users,
        "models": models,
        "config": config,
        "api_key_for": api_key_for,
    }
    if provider_factory is not None:
        call_kwargs["provider_factory"] = provider_factory
    raw = await do_call(**call_kwargs)
    return _wrap_results(raw, questions, rendered_users, models, include_prompts, system=system)


def add_parser(sub) -> None:
    p = sub.add_parser(
        "chat",
        help="질문 N개 × 모델 M개 매트릭스 (같은 게임/응원글 데이터 공유)",
        description=(
            "system + user 템플릿 + 질문 N개 + (game, cheers) 데이터 1세트를 받아 "
            "user 프롬프트 N개를 렌더하고 모델 M개에 비동기 매트릭스 호출. "
            "결과는 question별 그룹핑된 JSON으로 stdout."
        ),
    )
    p.add_argument("--system", default=None,
                   help="system 프롬프트 텍스트")
    p.add_argument("--system-file", default=None,
                   help="system 프롬프트 파일 (--system과 상호 배타)")
    p.add_argument("--user-template", default=None,
                   help="user jinja 템플릿 텍스트")
    p.add_argument("--user-template-file", default=None,
                   help="user jinja 템플릿 파일 (--user-template과 상호 배타)")
    p.add_argument("--question", action="append", default=[],
                   help="질문 텍스트 (반복 가능, 최소 1회)")
    p.add_argument("--game-data", default=None,
                   help="fetch 출력 JSON 파일 경로 또는 '-' (stdin). 필수")
    p.add_argument("--model", action="append", default=[],
                   help="provider:model (반복 가능, 최소 1회)")
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--max-tokens", type=int, default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--include-prompts", action="store_true",
                   help="결과 JSON에 렌더된 user 프롬프트 본문 포함")
    p.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> int:
    if not args.question:
        print("at least one --question is required", file=sys.stderr)
        return 2
    if not args.model:
        print("at least one --model is required", file=sys.stderr)
        return 2
    if not args.game_data:
        print("--game-data is required (path or '-' for stdin)", file=sys.stderr)
        return 2

    try:
        system = _resolve_system(args, {})
        user_template = _resolve_user_template(args)
        game_data = _resolve_game_data(args.game_data)
        models = _parse_model_flag(args.model)
    except (ValueError, FileNotFoundError) as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2

    cfg_dict: dict[str, Any] = {}
    if args.temperature is not None:
        cfg_dict["temperature"] = args.temperature
    if args.max_tokens is not None:
        cfg_dict["max_tokens"] = args.max_tokens
    config = LLMConfig(**cfg_dict) if cfg_dict else None

    settings = UnifiedChatSettings()
    try:
        out = asyncio.run(do_chat(
            system=system,
            user_template=user_template,
            questions=list(args.question),
            game_data=game_data,
            models=models,
            config=config,
            api_key_for=_settings_api_key_for(settings),
            include_prompts=args.include_prompts,
        ))
    except (TemplateSyntaxError, UndefinedError) as e:
        print(f"template error: {e}", file=sys.stderr)
        return 2

    write_output(out, args.out, fmt="json")

    has_error = any(r["error"] for r in out["results"])
    all_error = has_error and all(r["error"] for r in out["results"])
    return 1 if all_error else 0
