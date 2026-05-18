"""uctest prompts — 기본 system/user 프롬프트 템플릿을 stdout으로 출력.

에이전트가 unifiedchat 서버의 베이스 프롬프트를 참조해 자기 프롬프트를 작성한 뒤
`uctest call --system ... --user ...` 로 호출하는 워크플로우를 위한 read-only 도구.
실제 LLM 호출에는 관여하지 않는다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_VALID = ("system", "user", "list")


def add_parser(sub) -> None:
    p = sub.add_parser(
        "prompts",
        help="기본 system/user 프롬프트 템플릿 출력 (에이전트 참조용)",
    )
    p.add_argument(
        "which",
        nargs="?",
        default="list",
        choices=_VALID,
        help="system | user | list (default: list)",
    )
    p.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> int:
    if args.which == "list":
        for path in sorted(_TEMPLATE_DIR.glob("*.jinja")):
            sys.stdout.write(f"{path.stem}\t{path.name}\n")
        return 0
    fname = f"{args.which}.jinja"
    path = _TEMPLATE_DIR / fname
    if not path.exists():
        print(f"template not found: {fname}", file=sys.stderr)
        return 2
    sys.stdout.write(path.read_text(encoding="utf-8"))
    if not sys.stdout.isatty():
        sys.stdout.flush()
    return 0
