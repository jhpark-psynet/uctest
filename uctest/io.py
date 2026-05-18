"""YAML/JSON 입출력 헬퍼.

stdin '-' 처리, --out 파일 쓰기, format 선택을 한곳에 모아둔다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml


def read_input(path_arg: str) -> Any:
    """파일 경로 또는 '-'(stdin)에서 YAML/JSON 로드.

    yaml.safe_load는 JSON도 그대로 파싱한다.
    """
    if path_arg == "-":
        text = sys.stdin.read()
    else:
        text = Path(path_arg).read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("empty input")
    return yaml.safe_load(text)


def write_output(data: Any, out_path: str | None, fmt: str = "json") -> None:
    """stdout 또는 파일로 출력.

    fmt: 'json' (기본, indent=2) | 'yaml'
    """
    if fmt == "yaml":
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    if out_path:
        Path(out_path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
