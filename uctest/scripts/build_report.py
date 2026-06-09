"""Build a comparable HTML report from a chat matrix run.

Input:
- --game-data: fetch JSON ({"game": {...}, "cheers": [...]})
- --matrix:    one or more chat JSON (results[]); later files patch earlier
                errors by (question_idx, provider, model). Use this when a
                model fails mid-matrix and you re-run only that one.
- --config:    JSON with questions, models, optional pricing/eval. Schema:
    {
      "questions": ["...", "..."],
      "models": [
        {"provider": "gemini", "model": "gemini-3-flash-preview",
         "label": "Gemini 3 Flash", "price_in": 0.5, "price_out": 3.0}, ...
      ],
      "eval": {                          // optional — manual analysis
        "per_question": [{"title": "...", "summary": "...",
                           "rows": [["Label", "pass|partial|fail|truncated",
                                     "comment"], ...]}, ...],
        "overall_models": [{"label": "...", "strengths": "...",
                            "weaknesses": "...", "verdict": "...",
                            "highlight": "good|bad|null"}, ...],
        "improvements": [{"title": "A. ...", "items": ["...", "..."]}, ...]
      }
    }
- --output:    where to write the HTML.

Korean rendering uses uctest.prompt_builder._env so `tojson` matches
what was actually sent to LLMs (raw 한글, ensure_ascii=False).
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from uctest.prompt_builder import _env as _jinja_env

_USER_TPL = _jinja_env.get_template("user.jinja")
_SYSTEM_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "system.jinja"

CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', 'Apple SD Gothic Neo', sans-serif;
       margin: 0; padding: 2rem; background: #fafafa; color: #1a1a1a; line-height: 1.55; }
.container { max-width: 1280px; margin: 0 auto; }
h1 { font-size: 1.7rem; margin: 0 0 0.3rem; }
h2 { font-size: 1.3rem; margin: 2rem 0 0.6rem; padding-bottom: 0.3rem; border-bottom: 2px solid #2d2d2d; }
h3 { font-size: 1.05rem; margin: 1.2rem 0 0.5rem; color: #444; }
.meta { color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }
.card { background: white; border: 1px solid #e5e5e5; border-radius: 6px; padding: 1rem 1.2rem; margin: 0.8rem 0; }
details { background: white; border: 1px solid #e5e5e5; border-radius: 6px; margin: 0.5rem 0; }
details > summary { padding: 0.7rem 1rem; cursor: pointer; font-weight: 600; user-select: none; }
details[open] > summary { border-bottom: 1px solid #e5e5e5; }
details pre { margin: 0; padding: 1rem; overflow-x: auto; background: #f5f5f4; font-size: 0.82rem;
              line-height: 1.5; white-space: pre-wrap; word-break: break-word; border-radius: 0 0 6px 6px; }
table { border-collapse: collapse; width: 100%; margin: 0.5rem 0 1rem;
        background: white; border: 1px solid #d4d4d4; border-radius: 6px; overflow: hidden; }
th, td { padding: 0.7rem 0.9rem; text-align: left; vertical-align: top; border-bottom: 1px solid #ececec; }
th { background: #f0f0ef; font-weight: 600; font-size: 0.85rem; }
tr:last-child td { border-bottom: none; }
td.model { width: 18%; font-weight: 600; font-size: 0.9rem; }
td.model .sub { display:block; color:#666; font-size:0.78rem; font-weight:400; font-family: monospace; }
td.text { white-space: pre-wrap; word-break: break-word; font-size: 0.95rem; }
td.tok { width: 12%; font-family: monospace; font-size: 0.85rem; color: #555; text-align: right; }
.question-block { background: #eef4ff; border-left: 4px solid #3b6cd9; padding: 0.6rem 1rem;
                  border-radius: 4px; margin: 1rem 0 0.5rem; font-weight: 600; }
.policy-badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 3px;
                font-size: 0.72rem; font-weight: 600; margin-left: 0.4rem; }
.policy-pass { background: #d1fae5; color: #047857; }
.policy-partial { background: #fef3c7; color: #92400e; }
.policy-fail { background: #fee2e2; color: #991b1b; }
.policy-truncated { background: #fde0ff; color: #7b1d8a; }
.eval-table th, .eval-table td { font-size: 0.88rem; }
.row-good td { background: #efe; }
.row-bad td { background: #fee; }
.kbd { font-family: monospace; background: #f0f0ef; padding: 1px 6px; border-radius: 3px; font-size: 0.85rem; }
ul.findings li { margin: 0.4rem 0; }
.right { text-align: right; }
"""

BADGE = {
    "pass": ("정책 충족", "policy-pass"),
    "partial": ("부분 충족", "policy-partial"),
    "fail": ("미충족", "policy-fail"),
    "truncated": ("응답 잘림", "policy-truncated"),
}


def _esc(s: Any) -> str:
    return html.escape(str(s))


def _merge_matrices(paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge multiple matrix JSON files. Later results override earlier
    ones with the same (question_idx, provider, model). Errored earlier
    rows are dropped if a non-errored later row exists for the same key.

    Returns (merged_results, first_matrix_meta). `system_prompt` (if any
    file has it) is preserved in the meta — prefer the first occurrence.
    """
    all_results: dict[tuple[int, str, str], dict[str, Any]] = {}
    first_meta: dict[str, Any] = {}
    for i, p in enumerate(paths):
        data = json.loads(p.read_text())
        if i == 0:
            first_meta = {k: v for k, v in data.items() if k != "results"}
        elif "system_prompt" in data and "system_prompt" not in first_meta:
            first_meta["system_prompt"] = data["system_prompt"]
        for r in data["results"]:
            key = (r["question_idx"], r["provider"], r["model"])
            existing = all_results.get(key)
            if existing and not existing.get("error") and r.get("error"):
                continue  # don't overwrite good with new error
            all_results[key] = r
    return list(all_results.values()), first_meta


def _find_response(results: list[dict[str, Any]], qi: int, provider: str, model: str):
    for r in results:
        if r["question_idx"] == qi and r["provider"] == provider and r["model"] == model:
            return r
    return None


def _fmt_ms(ms: Any) -> str:
    if ms is None:
        return "-"
    return f"{int(ms):,} ms"


def _cell_response(r: dict[str, Any] | None) -> str:
    if r is None:
        return '<td class="text" colspan="3"><em style="color:#888">없음</em></td>'
    if r.get("error"):
        body = f'<em style="color:#c00">ERROR:</em> {_esc(r["error"])[:300]}'
        tok = "-"
    else:
        body = _esc(r["text"])
        tok = f'in {r["input_tokens"]}<br>out {r["output_tokens"]}'
    ms = _fmt_ms(r.get("elapsed_ms"))
    return f'<td class="text">{body}</td><td class="tok">{tok}</td><td class="tok">{ms}</td>'


def build_html(
    game: dict[str, Any],
    matrix_results: list[dict[str, Any]],
    matrix_meta: dict[str, Any],
    config: dict[str, Any],
) -> str:
    questions: list[str] = config["questions"]
    models: list[dict[str, Any]] = config["models"]
    evalcfg: dict[str, Any] = config.get("eval", {})

    # Prefer prompts captured at call time (chat --include-prompts). Fall back
    # to base templates only when the matrix JSON doesn't carry them — in that
    # case the report assumes the baseline was used and may diverge from
    # what was actually sent if the user supplied --system / --user-template.
    system_prompt = matrix_meta.get("system_prompt")
    system_prompt_source = "matrix"
    if system_prompt is None:
        system_prompt = _SYSTEM_TEMPLATE_PATH.read_text()
        system_prompt_source = "baseline (chat --include-prompts 미사용 — 변형 system이면 어긋날 수 있음)"

    # Build user_prompt lookup from matrix_results (one per question_idx).
    user_prompt_by_q: dict[int, str] = {}
    for r in matrix_results:
        if "user_prompt" in r and r["question_idx"] not in user_prompt_by_q:
            user_prompt_by_q[r["question_idx"]] = r["user_prompt"]

    rendered_users: list[str] = []
    user_prompt_source = "matrix" if user_prompt_by_q else "baseline (chat --include-prompts 미사용 — 커스텀 템플릿이면 어긋날 수 있음)"
    for qi, q in enumerate(questions):
        if qi in user_prompt_by_q:
            rendered_users.append(user_prompt_by_q[qi])
        else:
            rendered_users.append(_USER_TPL.render(
                data=game["game"], recent_cheers=game.get("cheers", []), question=q,
            ))

    parts: list[str] = []
    started_at = matrix_meta.get("started_at", "-")
    duration = matrix_meta.get("duration_seconds", 0)

    parts.append(f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>uctest 매트릭스 리포트 — {_esc(game['game'].get('home_team', ''))} vs {_esc(game['game'].get('away_team', ''))}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
<h1>uctest {len(questions)}Q × {len(models)}모델 매트릭스 리포트</h1>
<div class="meta">
  Run start: {_esc(started_at)} · Duration: {duration:.1f}s ·
  Generated: {datetime.now().isoformat(timespec='seconds')}
</div>

<div class="card">
<h3 style="margin-top:0">경기 (game_id: <span class="kbd">{_esc(game['game'].get('game_id', '-'))}</span>)</h3>
<table>
<tr><th>리그</th><td>{_esc(game['game'].get('league_name', '-'))}</td>
    <th>날짜·시각</th><td>{_esc(game['game'].get('match_date', ''))} {_esc(game['game'].get('match_time', ''))}</td></tr>
<tr><th>홈</th><td>{_esc(game['game'].get('home_team', ''))} ({_esc(game['game'].get('home_score', ''))})</td>
    <th>원정</th><td>{_esc(game['game'].get('away_team', ''))} ({_esc(game['game'].get('away_score', ''))})</td></tr>
<tr><th>상태</th><td>{_esc(game['game'].get('status', '-'))}</td>
    <th>응원글</th><td>최근 {len(game.get('cheers', []))}건</td></tr>
</table>
</div>

<h2>1. 최종 LLM에 전달된 프롬프트</h2>
<p style="color:#555;font-size:0.92rem;">
system 프롬프트는 모든 호출에 동일. user 프롬프트는 질문마다 다르게 렌더 (Jinja 슬롯: <span class="kbd">match_state</span>, <span class="kbd">recent_cheers</span>, <span class="kbd">question</span>).
</p>
<details>
  <summary>System 프롬프트 <span style="font-weight:400;color:#666">— 출처: {_esc(system_prompt_source)}</span></summary>
  <pre>{_esc(system_prompt)}</pre>
</details>
""")

    per_q_eval = evalcfg.get("per_question", [])
    for qi, q in enumerate(questions):
        notes = per_q_eval[qi] if qi < len(per_q_eval) else {}
        title = notes.get("title", f"Q{qi}")
        parts.append(f"""
<h2>2.{qi + 1} {_esc(title)}</h2>
<div class="question-block">질문: {_esc(q)}</div>
<details>
  <summary>이 질문에 실제로 전달된 user 프롬프트 <span style="font-weight:400;color:#666">— 출처: {_esc(user_prompt_source)}</span></summary>
  <pre>{_esc(rendered_users[qi])}</pre>
</details>
<h3>모델별 응답</h3>
<table>
<thead><tr><th style="width:18%">모델</th><th>응답</th><th class="right" style="width:11%">토큰</th><th class="right" style="width:10%">응답시간</th></tr></thead>
<tbody>
""")
        for m in models:
            r = _find_response(matrix_results, qi, m["provider"], m["model"])
            parts.append(
                f'<tr><td class="model">{_esc(m["label"])}<span class="sub">{_esc(m["provider"])}:{_esc(m["model"])}</span></td>{_cell_response(r)}</tr>'
            )
        parts.append("</tbody></table>")

        if notes.get("rows"):
            parts.append('<h3>정책 충족 평가</h3><table class="eval-table"><thead><tr><th>모델</th><th style="width:15%">판정</th><th>비고</th></tr></thead><tbody>')
            for row in notes["rows"]:
                label, verdict, comment = row[0], row[1], row[2]
                badge_text, badge_cls = BADGE.get(verdict, (verdict, ""))
                parts.append(f'<tr><td>{_esc(label)}</td><td><span class="policy-badge {badge_cls}">{_esc(badge_text)}</span></td><td>{_esc(comment)}</td></tr>')
            parts.append("</tbody></table>")
        if notes.get("summary"):
            parts.append(f'<p style="color:#444;font-size:0.92rem;"><strong>요약:</strong> {_esc(notes["summary"])}</p>')

    # ---- Overall evaluation ----
    overall = evalcfg.get("overall_models", [])
    if overall:
        parts.append("""
<h2>3. 종합 평가</h2>
<table class="eval-table">
<thead><tr><th>모델</th><th>강점</th><th>약점</th><th>총평</th></tr></thead>
<tbody>
""")
        for o in overall:
            cls = ""
            if o.get("highlight") == "good":
                cls = "row-good"
            elif o.get("highlight") == "bad":
                cls = "row-bad"
            parts.append(
                f'<tr class="{cls}"><td><strong>{_esc(o["label"])}</strong></td>'
                f'<td>{_esc(o.get("strengths", ""))}</td>'
                f'<td>{_esc(o.get("weaknesses", ""))}</td>'
                f'<td>{_esc(o.get("verdict", ""))}</td></tr>'
            )
        parts.append("</tbody></table>")

    # ---- Token totals + cost ----
    pricing = {(m["provider"], m["model"]): (m.get("price_in", 0.0), m.get("price_out", 0.0)) for m in models}
    totals: dict[tuple[str, str], list[int]] = {}
    latencies: dict[tuple[str, str], list[int]] = {}
    for r in matrix_results:
        if r.get("error"):
            continue
        key = (r["provider"], r["model"])
        totals.setdefault(key, [0, 0])
        totals[key][0] += r.get("input_tokens") or 0
        totals[key][1] += r.get("output_tokens") or 0
        ms = r.get("elapsed_ms")
        if ms is not None:
            latencies.setdefault(key, []).append(int(ms))

    def _latency_cell(key: tuple[str, str]) -> str:
        vals = latencies.get(key)
        if not vals:
            return "-"
        avg = sum(vals) / len(vals)
        return f"{avg:,.0f} ms<br><span style=\"color:#888;font-size:0.78rem\">min {min(vals):,} / max {max(vals):,}</span>"

    parts.append("""
<h2>4. 토큰·비용·응답시간 합계</h2>
<table class="eval-table">
<thead><tr><th>모델</th><th class="right">입력 합</th><th class="right">출력 합</th><th class="right">추정 비용 (USD)</th><th class="right">평균 응답시간</th></tr></thead>
<tbody>
""")
    total_cost = 0.0
    for m in models:
        key = (m["provider"], m["model"])
        tin, tout = totals.get(key, (0, 0))
        pin, pout = pricing[key]
        cost = (tin * pin + tout * pout) / 1_000_000
        total_cost += cost
        parts.append(
            f'<tr><td>{_esc(m["label"])}</td>'
            f'<td class="right">{tin:,}</td>'
            f'<td class="right">{tout:,}</td>'
            f'<td class="right">${cost:.5f}</td>'
            f'<td class="right">{_latency_cell(key)}</td></tr>'
        )
    parts.append(
        f'<tr style="font-weight:600;background:#f9f9f9"><td>합계</td><td class="right">-</td><td class="right">-</td><td class="right">${total_cost:.5f}</td><td class="right">-</td></tr>'
        "</tbody></table>"
    )

    # ---- Production cost projection (DAU·adoption·queries) ----
    projection = config.get("projection")
    if projection:
        dau = int(projection["dau"])
        adoption = float(projection["adoption_rate"])
        per_user = float(projection["queries_per_user"])
        krw_rate = projection.get("krw_per_usd")  # None이면 KRW 컬럼 생략
        daily_qa = dau * adoption * per_user
        num_q = max(len(questions), 1)
        krw_note = f" · 환율 가정 <strong>₩{krw_rate:,.0f}/USD</strong>" if krw_rate else ""
        def _money(usd: float) -> str:
            if krw_rate is None:
                return f"${usd:,.2f}"
            return f'${usd:,.2f}<br><span style="color:#666;font-size:0.82rem">₩{usd * krw_rate:,.0f}</span>'
        parts.append(f"""
<h3>4.1 운영 비용 추정 (DAU·채택률·1인당 Q&amp;A 가정)</h3>
<p style="color:#555;font-size:0.9rem;">
  가정: DAU <strong>{dau:,}</strong> · 챗 채택률 <strong>{adoption:.0%}</strong> · 1인당 <strong>{per_user:g} Q&amp;A/일</strong>{krw_note}
  → 일 Q&amp;A <strong>{daily_qa:,.0f}건</strong>.
  모델별 단가 = §4 표 비용 ÷ 매트릭스 질문 수({num_q}).
</p>
<table class="eval-table">
<thead><tr><th>모델</th><th class="right">단가 (USD/Q&amp;A)</th><th class="right">일 비용</th><th class="right">월 비용 (×30)</th><th class="right">연 비용 (×365)</th></tr></thead>
<tbody>
""")
        for m in models:
            key = (m["provider"], m["model"])
            tin, tout = totals.get(key, (0, 0))
            pin, pout = pricing[key]
            run_cost = (tin * pin + tout * pout) / 1_000_000
            per_qa = run_cost / num_q
            daily = per_qa * daily_qa
            monthly = daily * 30
            yearly = daily * 365
            parts.append(
                f'<tr><td>{_esc(m["label"])}</td>'
                f'<td class="right">${per_qa:.5f}</td>'
                f'<td class="right">{_money(daily)}</td>'
                f'<td class="right">{_money(monthly)}</td>'
                f'<td class="right">{_money(yearly)}</td></tr>'
            )
        parts.append("</tbody></table>")

    # ---- Improvements ----
    improvements = evalcfg.get("improvements", [])
    if improvements:
        parts.append('<h2>5. 개선 방향</h2>')
        for block in improvements:
            parts.append('<div class="card">')
            parts.append(f'<h3 style="margin-top:0">{_esc(block.get("title", ""))}</h3>')
            parts.append('<ul class="findings">')
            for item in block.get("items", []):
                parts.append(f'<li>{item}</li>')  # NOTE: allows inline HTML/<code> intentionally
            parts.append('</ul></div>')

    parts.append("</div></body></html>")
    return "".join(parts)


def _auto_output_path(game: dict[str, Any]) -> Path:
    """Default output path: testout/report-{home}-vs-{away}-{HHMM}.html.
    If a file with that name exists, append _2, _3, ... to avoid overwrites.
    """
    g = game["game"]
    home = (g.get("home_team") or "home").strip().replace("/", "_")
    away = (g.get("away_team") or "away").strip().replace("/", "_")
    hhmm = datetime.now().strftime("%H%M")
    base = Path("testout") / f"report-{home}-vs-{away}-{hhmm}.html"
    if not base.exists():
        return base
    stem, suffix = base.stem, base.suffix
    for n in range(2, 100):
        candidate = base.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"too many existing reports for {base}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game-data", required=True, type=Path, help="fetch JSON 경로")
    ap.add_argument("--matrix", required=True, type=Path, action="append",
                    help="chat 결과 JSON 경로. 여러 번 지정 가능 (재실행 머지)")
    ap.add_argument("--config", required=True, type=Path, help="questions/models/eval 정의 JSON")
    ap.add_argument("--output", type=Path,
                    help="출력 HTML 경로. 생략 시 testout/report-{home}-vs-{away}-{HHMM}.html")
    args = ap.parse_args()

    game = json.loads(args.game_data.read_text())
    config = json.loads(args.config.read_text())
    results, meta = _merge_matrices(args.matrix)

    output = args.output or _auto_output_path(game)
    html_out = build_html(game, results, meta, config)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_out, encoding="utf-8")
    print(f"wrote {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
