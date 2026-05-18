import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from uctest.schemas import Slots

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(
        disabled_extensions=("jinja",),
        default=False,
        default_for_string=False,
    ),
    trim_blocks=False,
    lstrip_blocks=False,
    keep_trailing_newline=False,
)
# Jinja의 기본 `| tojson`은 HTML 안전용으로 한글을 `\uXXXX`로, `<`·`>`·`&`·`'`를
# `<` 등으로 escape한다. LLM 프롬프트는 plain text라 그 변환이 가독성만
# 떨어뜨리고 토큰 수도 늘림. 커스텀 `plain_json` 필터로 raw json 덤프.
def _plain_json(value, indent=None):
    kwargs = {"sort_keys": True, "ensure_ascii": False}
    if indent is not None:
        kwargs["indent"] = indent
    return json.dumps(value, **kwargs)


_env.filters["tojson"] = _plain_json

_system_tpl = _env.get_template("system.jinja")
_user_tpl = _env.get_template("user.jinja")


def render(
    question: str,
    slots: Slots,
    *,
    system_template: str | None = None,
) -> tuple[str, str]:
    ctx_system = {
        "style": slots.style,
        "policy": slots.policy,
        "tools": slots.tools,
        "user_profile": slots.user_profile.model_dump() if slots.user_profile else None,
        "user_disposition": slots.user_disposition,
        # history 자체는 user 프롬프트에만 렌더되지만, system 템플릿이 history 유무
        # 기반으로 가이드 분기를 켜고 끄도록 컨텍스트에 노출한다.
        "history": slots.history,
        "character": slots.character.model_dump() if slots.character else None,
    }
    # turn.role / turn.content 접근 가능하도록 HistoryTurn 인스턴스를 그대로 넘긴다
    ctx_user = {
        "tone": slots.tone,
        "data": slots.data,
        "odds": slots.odds,
        "events": slots.events,
        "history": slots.history,
        "recent_cheers": slots.recent_cheers,
        "question": question,
    }
    sys_tpl = _env.from_string(system_template) if system_template else _system_tpl
    return sys_tpl.render(**ctx_system), _user_tpl.render(**ctx_user)
