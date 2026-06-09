"""uctest call — system + users + models → LLM 매트릭스 응답.

서버를 거치지 않고 LLMProvider 어댑터를 직접 사용해 users × models 풀 매트릭스를
asyncio.gather로 병렬 호출한다. DB 로깅 없음.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from uctest.config import UnifiedChatSettings
from uctest.llm.factory import LLMProviderFactory
from uctest.llm.provider import LLMConfig, LLMProvider

from uctest.io import read_input, write_output

_KST = ZoneInfo("Asia/Seoul")

# provider 이름 → UnifiedChatSettings 키 매핑 (CLI는 settings 한 곳으로만 env 본다)
_PROVIDER_KEY_ATTR = {
    "gemini": "gemini_api_key",
    "openai": "openai_api_key",
    "claude": "anthropic_api_key",
}


def _settings_api_key_for(settings: UnifiedChatSettings) -> Callable[[str], str]:
    def _key(provider: str) -> str:
        attr = _PROVIDER_KEY_ATTR.get(provider, "")
        return getattr(settings, attr, "") if attr else ""
    return _key


async def _timed(coro: Any) -> tuple[Any, int]:
    """단일 generate coro를 감싸 per-응답 latency(ms)를 잰다.

    매트릭스는 asyncio.gather로 동시 실행되므로 전체 duration_seconds로는
    모델별 응답 시간을 분리할 수 없다. 각 coro를 개별 타이머로 감싼다.
    예외는 삼켜서 (exc, elapsed_ms) 튜플로 반환 — gather가 멈추지 않게
    (호출부에서 isinstance(r, Exception)로 분기)."""
    t0 = time.perf_counter()
    try:
        r: Any = await coro
    except Exception as e:  # noqa: BLE001
        r = e
    return r, round((time.perf_counter() - t0) * 1000)


async def do_call(
    *,
    system: str,
    users: list[str],
    models: list[tuple[str, str] | list[str]],
    config: LLMConfig | None = None,
    provider_factory: Callable[[str, str, str], LLMProvider] = LLMProviderFactory.create,
    api_key_for: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """users × models 풀 매트릭스 비동기 호출.

    provider_factory / api_key_for를 테스트에서 주입할 수 있게 둠.
    """
    started = datetime.now(_KST)
    t0 = time.perf_counter()

    coros = []
    metas: list[tuple[int, str, str, str]] = []
    # factory 자체 실패(알 수 없는 provider 등)는 동기적으로 발생하므로
    # 더미 sentinel로 자리를 채워 gather 결과 인덱스를 맞춘다.
    factory_errors: dict[int, Exception] = {}
    for ui, user in enumerate(users):
        for entry in models:
            provider, model_name = entry[0], entry[1]
            api_key = api_key_for(provider) if api_key_for else ""
            metas.append((ui, user, provider, model_name))
            try:
                prov = provider_factory(provider, api_key, model_name)
                coros.append(prov.generate(system, user, config))
            except Exception as e:  # noqa: BLE001
                factory_errors[len(coros)] = e

                async def _raise(_e=e):
                    raise _e
                coros.append(_raise())

    raw = await asyncio.gather(*(_timed(c) for c in coros))

    results: list[dict[str, Any]] = []
    for (ui, user, provider, model_name), (r, elapsed_ms) in zip(metas, raw):
        if isinstance(r, Exception):
            results.append({
                "user_idx": ui, "user": user,
                "provider": provider, "model": model_name,
                "text": "",
                "input_tokens": None, "output_tokens": None,
                "elapsed_ms": elapsed_ms,
                "error": str(r),
            })
        else:
            results.append({
                "user_idx": ui, "user": user,
                "provider": provider, "model": model_name,
                "text": r.text,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "elapsed_ms": elapsed_ms,
                "error": None,
            })

    return {
        "started_at": started.isoformat(),
        "duration_seconds": round(time.perf_counter() - t0, 3),
        "results": results,
    }


def add_parser(sub) -> None:
    p = sub.add_parser(
        "call",
        help="LLM 호출 매트릭스 (users × models)",
        description=(
            "system + users + models를 LLM 매트릭스로 호출. "
            "입력 소스는 (1) positional YAML/JSON 파일 또는 stdin, "
            "(2) --system / --user / --user-file 직접 인자 — 둘 병행 가능. "
            "겹치는 필드는 인자가 input을 덮어쓴다."
        ),
    )
    p.add_argument(
        "input",
        nargs="?",
        default=None,
        help="입력 YAML/JSON 파일 또는 '-' (stdin). --system/--user만 쓸 거면 생략",
    )
    p.add_argument("--system", default=None,
                   help="system 프롬프트 텍스트 (input.system 덮어쓰기)")
    p.add_argument("--system-file", default=None,
                   help="system 프롬프트 파일 경로 (--system과 상호 배타)")
    p.add_argument("--user", action="append", default=[],
                   help="user 프롬프트 텍스트 (반복 가능, input.users 덮어쓰기)")
    p.add_argument("--user-file", action="append", default=[],
                   help="user 프롬프트 파일 (반복 가능, --user와 병합)")
    p.add_argument("--model", action="append", default=[],
                   help="provider:model (반복 가능, input.models 덮어쓰기)")
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--max-tokens", type=int, default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=_run)


def _parse_model_flag(flags: list[str]) -> list[list[str]]:
    out = []
    for f in flags:
        if ":" not in f:
            raise ValueError(f"--model expects 'provider:model' (got {f!r})")
        provider, model = f.split(":", 1)
        out.append([provider, model])
    return out


def _resolve_system(args: argparse.Namespace, payload: dict) -> str:
    if args.system is not None and args.system_file is not None:
        raise ValueError("--system and --system-file are mutually exclusive")
    if args.system is not None:
        return args.system
    if args.system_file is not None:
        return Path(args.system_file).read_text(encoding="utf-8")
    return payload.get("system", "")


def _resolve_users(args: argparse.Namespace, payload: dict) -> list[str]:
    users: list[str] = list(args.user)
    for path in args.user_file:
        users.append(Path(path).read_text(encoding="utf-8"))
    if users:
        return users
    payload_users = payload.get("users") or []
    if not isinstance(payload_users, list):
        raise ValueError("input.users must be a list")
    return payload_users


def _run(args: argparse.Namespace) -> int:
    if args.input is not None:
        try:
            payload = read_input(args.input)
        except (ValueError, FileNotFoundError) as e:
            print(f"input error: {e}", file=sys.stderr)
            return 2
    else:
        payload = {}

    try:
        system = _resolve_system(args, payload)
        users = _resolve_users(args, payload)
    except (ValueError, FileNotFoundError) as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2

    if not users:
        print(
            "users is empty (provide via --user / --user-file or input.users)",
            file=sys.stderr,
        )
        return 2

    try:
        cli_models = _parse_model_flag(args.model)
    except ValueError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    models = cli_models or payload.get("models") or []
    if not models:
        print("models is empty (provide in input.models or via --model)", file=sys.stderr)
        return 2

    cfg_dict = dict(payload.get("config") or {})
    if args.temperature is not None:
        cfg_dict["temperature"] = args.temperature
    if args.max_tokens is not None:
        cfg_dict["max_tokens"] = args.max_tokens
    config = LLMConfig(**cfg_dict) if cfg_dict else None

    settings = UnifiedChatSettings()
    out = asyncio.run(do_call(
        system=system,
        users=users,
        models=models,
        config=config,
        api_key_for=_settings_api_key_for(settings),
    ))
    write_output(out, args.out, fmt="json")

    has_error = any(r["error"] for r in out["results"])
    all_error = has_error and all(r["error"] for r in out["results"])
    if all_error:
        return 1
    return 0
