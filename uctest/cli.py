"""uctest — 데이터 fetch · LLM 호출 로컬 CLI 진입.

서브커맨드:
    prompts : 기본 system/user 프롬프트 템플릿 출력 (에이전트 참조용)
    games   : livescore 게임 목록 (game_id 고르기용 read-only)
    fetch   : livescore 단일 게임 + 응원글 JSON
    call    : system + users + models → LLM 매트릭스 응답 (raw)
    chat    : system + user 템플릿 + 질문 N + 데이터 1 + 모델 M → 매트릭스
"""
from __future__ import annotations

import argparse
import sys

import structlog


def _route_logs_to_stderr() -> None:
    """CLI의 stdout은 결과 데이터 채널이므로 structlog 출력은 stderr로 보낸다.

    unifiedchat 서버(`configure_logging`)도 console 핸들러를 stderr로 두지만, CLI는
    그 setup을 부르지 않으므로 structlog 기본(PrintLogger → stdout)이 적용돼
    JSON 파이프를 깨뜨린다. 가벼운 stderr-only 설정으로 대체.
    """
    structlog.configure(
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )


def main(argv: list[str] | None = None) -> int:
    _route_logs_to_stderr()
    parser = argparse.ArgumentParser(prog="uctest", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    from uctest import call as call_mod
    from uctest import chat as chat_mod
    from uctest import fetch as fetch_mod
    from uctest import games as games_mod
    from uctest import prompts as prompts_mod

    prompts_mod.add_parser(sub)
    games_mod.add_parser(sub)
    fetch_mod.add_parser(sub)
    call_mod.add_parser(sub)
    chat_mod.add_parser(sub)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
