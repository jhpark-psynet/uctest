# uctest

RasChat LLM 매트릭스 + livescore 데이터 fetch CLI 테스트 도구. 단독 패키지로 빌드·설치·실행이 가능하다.

## 구성

5개 서브커맨드를 가진 단일 CLI:

| 서브커맨드 | 역할 |
|---|---|
| `uctest prompts` | 기본 system/user 프롬프트 템플릿을 stdout으로 출력 (에이전트 참조용) |
| `uctest games`   | livescore 게임 목록 (read-only) — 에이전트가 game_id 고르기용 |
| `uctest fetch`   | livescore 단일 게임 + 응원글 JSON (`--game-id` 필요) |
| `uctest call`    | raw system + users + models 매트릭스를 LLM에 비동기 호출 (`users × models`) |
| `uctest chat`    | system + user 템플릿 + 질문 N + 데이터 1 + 모델 M → 매트릭스 (대화형) |

권장 워크플로우: 에이전트가 `uctest prompts system`/`uctest prompts user`로 베이스 템플릿을 확인 → 자신의 system/user 프롬프트를 구성 → `uctest call --system ... --user ...` 로 직접 인자 전달해 매트릭스 호출.

결과는 stdout(JSON/YAML), 로그는 stderr.

## 설치

```sh
cd /home/huto/dev/uctest
pip install -e .[all-llm,dev]
```

옵션 그룹:
- `claude` — anthropic SDK
- `openai` — openai SDK
- `all-llm` — claude + openai
- `dev` — pytest

`gemini`는 기본 의존성(google-genai)에 포함.

## 환경변수

`uctest.config.UnifiedChatSettings`가 읽는 주요 키:
- `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- `MSSQL_DSN` — fetch 서브커맨드에서 필수
- `MSSQL_POOL_SIZE`, `LIVESCORE_I18N_ENABLED`, `LIVESCORE_DEFAULT_CHEER_SIZE`

env 파일은 `.env` 자동 로드 (pydantic-settings).

추가로 `OPENSSL_CONF` — MSSQL 2014 TLS 호환용. 패키지 import 시 동봉
`openssl_legacy.cnf`를 자동 적용(`uctest/__init__.py`)하므로 보통 손댈 일은
없다. 다른 cnf를 쓰고 싶다면 export 한 값이 우선한다. pydantic-settings는
.env를 settings 모델로만 읽고 `os.environ`에 export 하지 않으므로,
`OPENSSL_CONF`는 .env에 넣어도 libssl이 못 본다 — 셸 export 또는 패키지
자동 설정에 의존.

## 사용 예

### 에이전트 워크플로우 (권장)

```sh
# 0) 베이스 템플릿 확인 — 에이전트가 unifiedchat 서버 프롬프트 구조 파악
uctest prompts list
uctest prompts system > /tmp/base_system.jinja
uctest prompts user   > /tmp/base_user.jinja

# 1-A) raw 매트릭스 — system/user 텍스트 자체를 그대로
uctest call \
  --system "$(cat my_system.txt)" \
  --user "$(cat user1.txt)" --user "$(cat user2.txt)" \
  --model gemini:gemini-2.5-flash \
  --model openai:gpt-4o-mini \
  > matrix.json

# 1-B) 대화형 — 한 경기 상황에 질문 N개를 던지는 흐름 (3 단계)

# 1-B-1) 어떤 게임이 진행 중인지 확인 → 에이전트가 game_id 선택
uctest games --sport S
# → {"date":"...", "sport":"S", "games":[{game_id, home, away, match_time, ...}, ...]}

# 1-B-2) 고른 game_id로 단일 게임 + 응원글 받기
uctest fetch --sport S --game-id 20260518001 --cheer-size 20 > /tmp/g.json

# 1-B-3) chat에 데이터 + 질문 + 모델 매트릭스 호출
uctest chat \
  --system "$(cat my_system.txt)" \
  --user-template-file my_user.jinja \
  --question "다음 5분 흐름은?" \
  --question "현재 베팅 가치는?" \
  --game-data /tmp/g.json \
  --model gemini:gemini-2.5-flash \
  --model openai:gpt-4o-mini \
  > chat.json

# 또는 셸 파이프로 2~3 단계를 한 줄에:
uctest fetch --sport S --game-id 20260518001 --cheer-size 20 | \
  uctest chat ... --game-data -
```

`call`은 `--system-file`, `--user-file`로 파일 경로 직접 전달도 가능 (`--user`/`--user-file` 병행 시 합쳐짐).
`chat`은 `--user-template`(텍스트)/`--user-template-file`(경로) 중 택1, `--game-data`는 fetch 출력 단일 게임 모드(`{date, sport, game, cheers}`) JSON 필수.

## 테스트

```sh
pytest tests
```

## 알려진 주의사항

- `livescore/pool.py`가 `fastapi.concurrency`(스레드풀 awaiter)를 쓰므로 fastapi가 의존성에 포함됨. uctest CLI는 서버를 띄우지 않지만 패키지가 따라 깔린다.
- MSSQL 2014 TLS: `openssl_legacy.cnf`가 repo 루트에 동봉. 패키지 import 시 `OPENSSL_CONF`로 자동 설정된다(`uctest/__init__.py`). 이게 없으면 `pyodbc 08001 / TCP 10054`로 핸드셰이크 거부됨. wheel 비-편집 설치 시엔 cnf가 빠질 수 있으니 사용자가 직접 export.
