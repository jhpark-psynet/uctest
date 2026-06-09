from pydantic_settings import BaseSettings


class UnifiedChatSettings(BaseSettings):
    unifiedchat_default_provider: str = "gemini"
    unifiedchat_default_model: str = "gemini-2.5-flash"
    unifiedchat_default_temperature: float = 0.3

    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    database_url: str = "postgresql://unifiedchat:unifiedchat_dev@localhost:5432/unifiedchat"
    app_env: str = "development"
    log_level: str = "INFO"
    log_dir: str = "logs"

    # 라이브스코어 MSSQL — 비어있으면 /livescore/* 라우터가 503 반환
    mssql_dsn: str = ""
    mssql_pool_size: int = 5
    livescore_default_cheer_size: int = 30
    livescore_i18n_enabled: bool = True

    # psynet DATA30 HTTP API — baseball fetch 경로
    data30_base_url: str = ""
    data30_auth_key: str = ""

    # 로컬 OpenAI-compatible LLM 엔드포인트. provider 토큰별로 분리:
    #   local:    범용 (하위호환)   ← LOCAL_LLM_BASE_URL
    #   lmstudio: LM Studio        ← LMSTUDIO_BASE_URL (기본 :1234)
    #   vllm:     vLLM             ← VLLM_BASE_URL     (기본 :8000)
    # 식별 핑거프린트: LM Studio는 GET /api/v0/models=200, vLLM은 GET /version={"version":...}.
    local_llm_base_url: str = "http://localhost:8000/v1"
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    vllm_base_url: str = "http://localhost:8000/v1"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = UnifiedChatSettings()
