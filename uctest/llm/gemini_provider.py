import structlog
from google import genai
from google.genai.types import GenerateContentConfig

from .provider import LLMProvider, LLMConfig, LLMResponse

logger = structlog.get_logger()


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    async def generate(
        self,
        system: str,
        user: str,
        config: LLMConfig | None = None,
    ) -> LLMResponse:
        config = config or LLMConfig()
        genai_config = GenerateContentConfig(
            system_instruction=system,
            temperature=config.temperature,
            max_output_tokens=config.max_tokens,
        )
        if config.response_format == "json":
            genai_config.response_mime_type = "application/json"
        logger.debug("llm.generate.start", model=self.model_name)
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=user,
                config=genai_config,
            )
        except Exception as e:
            logger.error("llm.generate.error", model=self.model_name, error=str(e))
            raise
        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
        output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
        return LLMResponse(
            text=response.text or "",
            raw={"model": self.model_name},
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
