from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SpParam:
    name: str
    value: Any

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("SpParam.name must not be empty")


@dataclass
class SpResult:
    rows: list[dict[str, Any]]
    out_values: dict[str, Any]


def call_sp_sync(
    conn: Any,
    sp_name: str,
    in_args: list[SpParam],
    out_specs: list[str],
) -> SpResult:
    """T-SQL EXEC sp_name @args 패턴으로 stored procedure 호출.

    pyodbc는 OUT 파라미터를 직접 바인딩하지 못해, NVARCHAR 변수 DECLARE 후
    @x OUTPUT으로 넘기고 트레일링 SELECT로 OUT 값을 두 번째 result set에서 읽는다.
    """
    placeholders = ", ".join(["?"] * len(in_args))
    if out_specs:
        decls = "\n".join(f"DECLARE @{n} NVARCHAR(4000);" for n in out_specs)
        out_params = ", ".join(f"@{n} OUTPUT" for n in out_specs)
        select_outs = ", ".join(f"@{n} AS {n}" for n in out_specs)
        sep = ", " if in_args else ""
        sql = (
            f"{decls}\n"
            f"EXEC {sp_name} {placeholders}{sep}{out_params};\n"
            f"SELECT {select_outs};"
        )
    else:
        sql = f"EXEC {sp_name} {placeholders};" if in_args else f"EXEC {sp_name};"

    cur = conn.cursor()
    try:
        cur.execute(sql, [p.value for p in in_args])
        rows: list[dict[str, Any]] = []
        out_values: dict[str, Any] = {}
        if cur.description:
            cols = [d[0] for d in cur.description]
            for r in cur.fetchall():
                if isinstance(r, tuple):
                    rows.append(dict(zip(cols, r, strict=False)))
                else:
                    rows.append({c: getattr(r, c, None) for c in cols})
        if out_specs:
            cur.nextset()
            if cur.description:
                cols = [d[0] for d in cur.description]
                out_row_raw = cur.fetchall()
                if out_row_raw:
                    first = out_row_raw[0]
                    if isinstance(first, tuple):
                        out_row = dict(zip(cols, first, strict=False))
                    else:
                        out_row = {c: getattr(first, c, None) for c in cols}
                    out_values = {n: out_row.get(n) for n in out_specs}
        return SpResult(rows=rows, out_values=out_values)
    finally:
        cur.close()
