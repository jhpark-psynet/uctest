import structlog
import anthropic
from .provider import LLMProvider, LLMConfig, LLMResponse

logger = structlog.get_logger()


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str = "claude-sonnet-4-6"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model_name = model_name

    async def generate(self, system: str, user: str, config: LLMConfig | None = None) -> LLMResponse:
        config = config or LLMConfig()
        system_prompt = system
        if config.response_format == "json":
            system_prompt = system + "\n\nJSON으로 응답하라."
        logger.debug("llm.generate.start", model=self.model_name)
        try:
            message = await self.client.messages.create(
                model=self.model_name,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as e:
            logger.error("llm.generate.error", model=self.model_name, error=str(e))
            raise
        text = message.content[0].text if message.content else ""
        usage = getattr(message, "usage", None)
        return LLMResponse(
            text=text,
            raw={"model": self.model_name},
            input_tokens=getattr(usage, "input_tokens", None) if usage else None,
            output_tokens=getattr(usage, "output_tokens", None) if usage else None,
        )
