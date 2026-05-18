# AGENTS.md — uctest 외부 에이전트 가이드

LIVE 스코어 챗봇용 system/user 프롬프트를 여러 LLM에 같은 입력으로 던져 응답을 비교하는 CLI. 5개 서브커맨드. stdout = 데이터(JSON), stderr = 로그. 도메인 지식은 코드에 들지 않고 인자로 받는다.

이 문서는 에이전트 1차 anchor. 인자 상세는 `uctest <cmd> --help`가 진실원.

## Setup 체크

fresh clone이면 venv부터 만든다 (gitignored, 클론 시 빠짐):
```sh
python -m venv .venv
.venv/bin/pip install -e .[all-llm,dev]
```
(uv 사용 시 `uv venv && uv pip install -e .[all-llm,dev]`. 자세한 옵션은 README "설치" 섹션.)

세팅됐는지 확인:
```sh
.venv/bin/uctest --help                # 서브커맨드 5개가 보이면 OK
```

API 키(`GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`)와 `MSSQL_DSN`은 `.env`로 자동 로드 (pydantic-settings). `.env`는 gitignored — 새로 깐 경우 직접 작성. `OPENSSL_CONF`는 패키지 import 시 `uctest/__init__.py`가 동봉 `openssl_legacy.cnf`로 자동 setdefault — **에이전트는 손대지 말 것**. (SQL Server 2014 TLS 호환용 — 안 걸면 fetch가 `pyodbc 08001 / 10054`로 깨짐.)

## 작업 시작 전 — 모델은 사용자에게 묻는다

`call` / `chat` 매트릭스를 띄우기 전 **어느 provider·model을 쓸지 사용자에게 확인**한다. 비용·속도·답변 톤·길이 편차가 크므로 디폴트로 박지 말 것. 사용자가 명시 안 하면 묻고 진행.

### 후보 모델 (2026-05 기준)

`provider:model` 토큰으로 `--model` 인자에 전달. **GPT 4.x는 후보 제외** (5.x로 일원화). Gemini는 2.5 deprecation(2026-06-17) 이전에 **3.x 시리즈로 통일**.

가격은 **USD per 1M tokens** (input / output). 매트릭스 1회 비용은 `Σ (in × $in + out × $out) / 1,000,000` 로 추정.

| Provider | Model | $ in / out | 용도 |
|---|---|---|---|
| **gemini** | `gemini-3.1-flash-lite-preview` | 0.25 / 1.50 | 가장 저렴, smoke |
| **gemini** | `gemini-3-flash` | 0.50 / 3.00 | 균형 (Pro급 지능 + Flash 가격) |
| **gemini** | `gemini-3.1-pro-preview` | 2.00 / 12.00 | 정밀 (preview) |
| **claude** | `claude-haiku-4-5` | 1.00 / 5.00 | 빠름·저렴 |
| **claude** | `claude-sonnet-4-6` | 3.00 / 15.00 | 균형 (1M ctx) |
| **claude** | `claude-opus-4-7` | 5.00 / 25.00 | 정밀, extended thinking |
| **openai** | `gpt-5.4-nano` | 0.20 / 1.25 | 가장 저렴 |
| **openai** | `gpt-5.4-mini` | 0.75 / 4.50 | 빠름 |
| **openai** | `gpt-5.4` | 2.50 / 15.00 | 균형 |
| **openai** | `gpt-5.5` | 5.00 / 30.00 | 정밀 (1.05M ctx) |

비용 감 잡기 — 입력 ~3000 tok × 출력 ~100 tok 한 응답 기준 단가 (USD):

| Tier | gemini | claude | openai |
|---|---|---|---|
| 가장 저렴 | flash-lite ~0.001 | — | nano ~0.001 |
| 빠름 | — | haiku ~0.004 | mini ~0.003 |
| 균형 | flash ~0.002 | sonnet ~0.011 | 5.4 ~0.009 |
| 정밀 | pro-preview ~0.007 | opus ~0.018 | 5.5 ~0.018 |

3사 균형 매트릭스 (Q × 3모델) 1 사이클 ≈ $0.02~0.04. 정밀 매트릭스는 ≈ $0.05~0.10.

추론(reasoning) 특화 — 별도:
- `openai:o3` (current), `openai:o3-pro`. `o3-mini`·`o4-mini`는 deprecated.
- Claude·Gemini는 별도 reasoning 모델 없음. 본 모델이 thinking 내장 (`claude-opus-4-7` extended thinking, `gemini-3.*` thinking budget).

주의:
- `gpt-5.5-mini` / `gpt-5.5-nano`는 **공식 존재하지 않음** (2026-05-18 OpenAI API 직접 확인). 5.5 라인은 `gpt-5.5` / `gpt-5.5-pro` 둘뿐. 작은 변형은 5.4 시리즈만.
- `gemini-3.1-pro-preview` / `gemini-3.1-flash-lite-preview`는 preview 상태 — stable Pro는 GA 전. preview 피하려면 `gemini-3-flash` 1종으로 갈음.
- Anthropic ID는 dateless 형태도 모두 pinned snapshot (evergreen 아님). snapshot 명시가 필요하면 `claude-haiku-4-5-20251001` 같은 dated 변형 사용.

곧 EOL되어 새 작업에선 쓰지 말 것:
- `gemini-2.5-*` — 2026-06-17 deprecated (Vertex AI는 10-16)
- `gemini-2.0-*` — 2026-06-01 종료
- `gpt-5.2-chat-latest` / `gpt-5.3-chat-latest` — 2026-05-08 제거됨
- `gpt-4o-*` / `gpt-4.1-*` — 동작은 하나 후보에서 명시적으로 제외

### 진행 규칙

- 사용자가 "3사 비교"·"전부 매트릭스" → 위 표 **균형** 컬럼 3개로 시작.
- 사용자가 "빠르게"·"smoke" → **빠름·저렴** 컬럼.
- 사용자가 "정밀"·"품질 검증" → **정밀·큰 모델** 컬럼.
- 그 외 모호한 경우 → "어떤 모델로 돌릴까요? (예: 빠른 3사 매트릭스 / 큰 모델 정밀 비교)" 한 번 묻고 진행.

## 5 서브커맨드

| 명령 | 역할 | 외부 의존성 |
|---|---|---|
| `prompts {list,system,user}` | 동봉 system/user.jinja 텍스트 dump | 없음 |
| `games --sport S` | 오늘 게임 목록 (game_id 픽업용) | MSSQL |
| `fetch --sport S --game-id <id> [--cheer-size N]` | 단일 게임 + 응원글 JSON | MSSQL |
| `call --system ... --user ... --model provider:model` | system × users × models 매트릭스 (raw) | LLM API |
| `chat --system ... --user-template-file ... --question ... --game-data ... --model ...` | user는 Jinja 템플릿 + 질문 N개로 렌더, models M개 매트릭스 | LLM API |

sport 코드: `S` 축구, `B` 야구, `K` 농구, `V` 배구, `H` 핸드볼, `T` 테니스 (오늘 진행 중인 종목만 채워짐).

provider 토큰: `gemini`, `claude`, `openai`. 예: `--model gemini:gemini-2.5-flash`, `--model claude:claude-haiku-4-5`, `--model openai:gpt-4o-mini`.

## 베이스 템플릿 확인

```sh
.venv/bin/uctest prompts list           # system / user 두 개
.venv/bin/uctest prompts system | less  # 정책 + 스타일 자동 선택 + policy
.venv/bin/uctest prompts user | less    # 슬롯(jinja) 구조
```

`system.jinja` 핵심: **스타일 자동 선택** — 세 신호(① 사용자 메시지 톤, ② match_state 양상, ③ recent_cheers 분위기)를 종합해 `hype_booster` / `chill_buddy` / `witty_joker` 중 하나로 답한다. 스타일 이름·라벨·JSON·코드블록은 본문에 노출 금지. 응원글의 욕설·비하는 어휘 흡수 없이 분위기만 추상화. `<policy>` 블록(사실 기반·베팅 권유 금지·미성년자 안전·채널 분위기 모방 금지)이 가장 강한 신호.

`user.jinja` 슬롯: `data`(match_state, tojson 직렬화), `odds`, `history`, `recent_cheers`, `question`.

## 골든 패스 — 한 사이클

```sh
# 1) 오늘 진행 중인 게임 목록 → game_id 하나 골라잡기
.venv/bin/uctest games --sport S 2>/dev/null | jq '.games[:5] | .[] | {game_id, home_team, away_team, status}'

# 2) 게임 데이터 + 최근 응원글 20건
.venv/bin/uctest fetch --sport S --game-id <위에서 고른 id> --cheer-size 20 > /tmp/g.json 2>/dev/null

# 3) system은 베이스 그대로, 질문 N개 × 모델 3사 매트릭스
.venv/bin/uctest chat \
  --system "$(.venv/bin/uctest prompts system)" \
  --user-template-file uctest/templates/user.jinja \
  --question "지금 분위기 어때?" \
  --question "팬들 반응 한 줄 요약" \
  --game-data /tmp/g.json \
  --model gemini:gemini-2.5-flash \
  --model claude:claude-haiku-4-5 \
  --model openai:gpt-4o-mini \
  > /tmp/m.json 2>/dev/null

# 4) 결과 비교 (질문·프로바이더 정렬)
jq -r '.results | sort_by(.question_idx, .provider) | .[] |
       "[\(.provider)/\(.model) | Q\(.question_idx) | in=\(.input_tokens) out=\(.output_tokens)]\n\(.text)\n"' /tmp/m.json
```

## Template override 규칙 (헷갈리는 부분)

- **`--system` 은 렌더되지 않는다.** chat/call이 받은 문자열을 그대로 LLM에 보낸다. Jinja 마커(`{{ }}`, `{% %}`)가 든 텍스트를 넘기면 마커가 그대로 LLM에 노출된다.
  - 베이스 `system.jinja`는 **이미 plain text 정책 문서** → `--system "$(uctest prompts system)"`로 그대로 넘기는 게 정상.
  - 변형 실험: 평문으로 직접 작성하거나, 자기 system 텍스트를 파일로 저장 후 `--system-file ./my_system.txt`.

- **`--user-template` / `--user-template-file` 은 Jinja로 렌더된다.** chat이 각 질문마다 `{**game_data, "question": q}` 컨텍스트로 렌더 후 LLM에 보낸다.
  - **alias 매핑**: fetch JSON의 `game` → 템플릿 변수 `data`, `cheers` → `recent_cheers`. 기존 키도 동시 노출(`{{ game.home_team }}` 같은 raw 접근도 작동). 구현: `uctest/chat.py:_render_users`.
  - 베이스 `user.jinja`는 `data`/`recent_cheers`/`odds`/`history`/`question` 슬롯 사용 — fetch 출력만 넘기면 `data`/`recent_cheers` 자동 채워짐. `odds`/`history`는 fetch 출력에 없어 `{% if %}` 가드로 블록 생략됨 (정상).

- **렌더 결과 디버깅**: `chat --include-prompts`를 추가하면 결과 JSON의 각 `results[].user_prompt`에 렌더된 user 본문이 같이 박혀 나옴. 슬롯이 비어 보이면 여기로 원인 추적.

- **`call` 의 user는 raw**: `call --user "..."`는 텍스트 그대로 (Jinja 렌더 없음, alias 없음). 템플릿 + 데이터 흐름이 필요하면 `chat`을 써야 한다.

## 출력 JSON 스키마

| 명령 | 최상위 키 | 핵심 필드 |
|---|---|---|
| `games` | `{date, sport, games[]}` | `games[].{game_id, home_team, away_team, home_score, away_score, status, league_name}` |
| `fetch` | `{date, sport, game, cheers}` | `game` = 위 games[]의 한 항목과 동형, `cheers` = `list[str]` (최근순) |
| `call` | `{started_at, duration_seconds, results[]}` | `results[].{user_idx, user, provider, model, text, input_tokens, output_tokens, error}` |
| `chat` | `{started_at, duration_seconds, questions, models, results[]}` | `results[].{question_idx, question, provider, model, text, input_tokens, output_tokens, error}` (+ `user_prompt` if `--include-prompts`) |

종료 코드: 0 정상 / 1 모든 결과 error / 2 입력 검증 실패 / 3 환경 미설정(MSSQL_DSN 등).

## Iteration 패턴

- **모델 비교**: 같은 system·user에 `--model` 여러 개 → 토큰·길이·톤·정책 준수 차이 한눈에 본다.
- **프롬프트 A/B**: system 텍스트 두 버전(`/tmp/sys_a.txt`, `/tmp/sys_b.txt`)을 각각 `--system-file`로 두 매트릭스 돌린 뒤 `jq`로 같은 question_idx끼리 diff.
- **데이터 비교**: 다른 game_id로 fetch → 같은 프롬프트 재실행. 같은 게임에서 여러 사이클 돌릴 땐 `/tmp/g.json` 재사용해 MSSQL 부담 줄임.
- **질문 N개 한 번에**: `chat --question "..." --question "..."` 반복. 데이터 1세트가 모든 질문에 공유돼 fetch는 1회로 끝남.

## Gotchas

- **로그 vs 데이터**: `uctest` 모든 명령은 stderr로 로그, stdout으로만 JSON. `2>&1`로 묶으면 jq 파싱 깨짐. 항상 `2>/tmp/err` 또는 `2>/dev/null`.
- **`.env`에 OPENSSL_CONF 넣지 말 것**: pydantic-settings는 .env를 settings 모델로만 읽고 `os.environ`에 export 안 한다. libssl이 못 봐서 효과 없음. 자동 setdefault는 `uctest/__init__.py`가 처리.
- **`--system`에 Jinja 파일 넘기지 말 것**: 렌더 안 되니 `{{ ... }}`가 LLM에 그대로 간다. 정책 텍스트는 plain text로.
- **`match_state` 직렬화**: 베이스 `user.jinja`는 `{{ data | tojson(indent=2) }}`로 한글 raw + 보기 좋은 JSON 출력. 커스텀 템플릿에서 `{{ data }}` 그대로 쓰면 Python dict repr(`{'key': 'val'}`)이 됨 — LLM은 파싱하지만 토큰 효율·가독성 ↓.
- **모델별 길이 편차**: 같은 system에도 gemini는 chill_buddy로 15 tokens까지 떨어질 수 있고 claude는 120+ 토큰까지 늘어남. 길이 하한은 의도적으로 미적용. 결과 해석 시 토큰 수도 같이 본다.
- **chat은 system 비어도 동작**: 그러나 정책 가드 0이 되어 LLM이 자유롭게 응원글 욕설을 인용할 수 있다. 보통 베이스 `system.jinja`로 시작.
- **MSSQL TCP는 사내망 필요**: 외부에서 1433 reachable 확인 필요. `games`/`fetch`만 영향.

## 더 깊이 알고 싶으면

| 파일 | 무엇이 있나 |
|---|---|
| `uctest/templates/system.jinja` | 정책 + 스타일 자동 선택 + `<policy>` 블록 |
| `uctest/templates/user.jinja` | 슬롯 구조 (`data`, `recent_cheers`, `odds`, `history`, `question`) |
| `uctest/cli.py` | 서브커맨드 라우팅 + import 순서 |
| `uctest/chat.py` | `_render_users`의 alias 매핑, `do_chat` 매트릭스 흐름 |
| `uctest/call.py` | `do_call` asyncio.gather, provider 어댑터 호출 |
| `uctest/__init__.py` | OPENSSL_CONF 자동 setdefault (libssl 로드 전) |
| `uctest/config.py` | `.env`로 읽는 키 전체 목록 |
| `tests/test_chat.py`, `tests/test_call.py` | 실행 가능한 계약. 모의 provider로 매트릭스·매핑 동작 검증 |
