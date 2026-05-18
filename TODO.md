# uctest — 다음 세션 인계 노트

작성: 2026-05-18 · 새 세션은 `/home/huto/dev/uctest/`를 CWD로 시작하라.

## 현재 상태

- standalone 완전 독립. `unifiedchat`과의 vendor sync 정책 폐기 — 이 트리는 자체적으로 진화한다.
- 설치: `.venv` 존재 (`python -m venv .venv` + `pip install -e .[all-llm,dev]` 완료).
- 단위 테스트: `.venv/bin/pytest tests -x` → 통과 (compose 제거 후 재확인).
- CLI 5개 서브커맨드: `prompts`, `games`, `fetch`, `call`, `chat`.
- LLM 실호출 smoke 완료 (gemini/claude/openai 3사).
- MSSQL livescore (`games`/`fetch`) 동작 확인. SQL Server 2014 TLS 호환을 위해 `openssl_legacy.cnf`를 repo 루트에 동봉, `uctest/__init__.py`가 import 시 `OPENSSL_CONF` 자동 설정.
- 외부 에이전트용 단일 가이드 `AGENTS.md` 리포 루트에 작성 (2026-05-18). 기존 `docs/skills/uctest/` 트리는 deprecated 콘텐츠 다수라 전체 삭제.
- 정리 (2026-05-18): `compose` 서브커맨드 + `scenario_composer.py` + `scripts/run_scenario.py` 제거. axes/question 레지스트리 모드 미사용.

## 우선순위 To-Do

### 1. git 저장소화
이 디렉토리는 untracked. 필요해지면:
```sh
cd /home/huto/dev/uctest
echo -e ".venv/\n__pycache__/\n.pytest_cache/\n.env\n*.egg-info/" > .gitignore
git init
git add -A && git commit -m "uctest 0.1.0 — standalone"
```
`.env` 커밋 금지 (시크릿). 첫 커밋 전에 `.gitignore` 반드시.

## 참고

- 기존 unifiedchat 설계 spec: `/home/huto/dev/unifiedchat/docs/superpowers/specs/2026-05-17-uctest-cli-design.md` (이력 참고용. 현 코드와는 불일치 — compose 제거 등)
- 분리 plan: `/home/huto/.claude/plans/lovely-strolling-lampson.md`
