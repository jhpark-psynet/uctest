"""uctest 패키지 import 시 가장 먼저 실행되는 초기화.

`OPENSSL_CONF`를 동봉 `openssl_legacy.cnf`로 설정해야 MSSQL 2014 TLS 핸드셰이크
(`pyodbc 08001 / 10054`)가 통과한다. 이 변수는 libssl 첫 로드 직전에 환경에
들어가 있어야 하므로, 어떤 서브모듈(특히 structlog/llm provider)이 SSL을
초기화하기 전에 패키지 최상단에서 처리한다.

사용자가 이미 `OPENSSL_CONF`를 export 했으면 그쪽을 존중. cnf 파일이 없으면
(non-editable wheel 등) 조용히 패스해 사용자가 직접 export 하도록 둔다.
"""
from __future__ import annotations

import os as _os
from pathlib import Path as _Path

if "OPENSSL_CONF" not in _os.environ:
    _cnf = _Path(__file__).resolve().parent.parent / "openssl_legacy.cnf"
    if _cnf.is_file():
        _os.environ["OPENSSL_CONF"] = str(_cnf)
