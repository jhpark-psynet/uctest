"""uctest prompts 단위 테스트.

system/user 템플릿 dump가 templates 디렉토리 내용과 일치하는지 검증.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uctest.prompts import _run

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "uctest" / "templates"


class _Args:
    def __init__(self, which: str) -> None:
        self.which = which


def test_prompts_system_dumps_template(capsys):
    rc = _run(_Args("system"))
    out = capsys.readouterr().out
    assert rc == 0
    assert out == (_TEMPLATE_DIR / "system.jinja").read_text(encoding="utf-8")


def test_prompts_user_dumps_template(capsys):
    rc = _run(_Args("user"))
    out = capsys.readouterr().out
    assert rc == 0
    assert out == (_TEMPLATE_DIR / "user.jinja").read_text(encoding="utf-8")


def test_prompts_list_shows_available(capsys):
    rc = _run(_Args("list"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "system" in out
    assert "user" in out
    assert "system.jinja" in out
    assert "user.jinja" in out
