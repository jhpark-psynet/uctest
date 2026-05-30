import structlog
import openai as openai_sdk
from .provider import LLMProvider, LLMConfig, LLMResponse

logger = structlog.get_logger()


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str = "gpt-4o",
                 base_url: str | None = None):
        # base_url 지정 시 vLLM/Ollama/LM Studio 등 OpenAI-compatible 엔드포인트로
        # 라우팅. None이면 클라우드 OpenAI 기본 URL.
        self.client = openai_sdk.AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name

    async def generate(self, system: str, user: str, config: LLMConfig | None = None) -> LLMResponse:
        config = config or LLMConfig()
        logger.debug("llm.generate.start", model=self.model_name)
        kwargs: dict = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        # gpt-5*, o1*, o3* 등 reasoning 계열은 max_completion_tokens + temperature 고정.
        # reasoning_effort 지정 — 짧은 max_tokens(예: 400)에서 reasoning이 토큰을 다
        # 먹고 visible 답이 비는 사고를 방지.
        # 모델별로 지원값 다름:
        #   gpt-5* (공식 OpenAI):       minimal/low/medium/high
        #   gpt-5.4-* (사용자 env):     none/low/medium/high/xhigh — 'minimal' 거부
        #   o1/o3/o4:                   기본값 유지 (기존 동작 보존)
        if self.model_name.startswith(("gpt-5", "o1", "o3", "o4")):
            kwargs["max_completion_tokens"] = config.max_tokens
            if self.model_name.startswith("gpt-5.4"):
                kwargs["reasoning_effort"] = "low"
            elif self.model_name.startswith("gpt-5"):
                kwargs["reasoning_effort"] = "minimal"
        else:
            kwargs["max_tokens"] = config.max_tokens
            kwargs["temperature"] = config.temperature
        try:
            response = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.error("llm.generate.error", model=self.model_name, error=str(e))
            raise
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        return LLMResponse(
            text=text,
            raw={"model": self.model_name},
            input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        )
