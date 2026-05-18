from .provider import LLMProvider
from .gemini_provider import GeminiProvider
from .claude_provider import ClaudeProvider
from .openai_provider import OpenAIProvider


class LLMProviderFactory:
    PROVIDERS: dict[str, type[LLMProvider]] = {
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
    }

    @classmethod
    def create(cls, provider: str, api_key: str, model_name: str) -> LLMProvider:
        provider_cls = cls.PROVIDERS.get(provider)
        if not provider_cls:
            raise ValueError(
                f"Unknown LLM provider: {provider}. "
                f"Available: {list(cls.PROVIDERS.keys())}"
            )
        return provider_cls(api_key=api_key, model_name=model_name)

    @classmethod
    def register(cls, name: str, provider_cls: type[LLMProvider]) -> None:
        cls.PROVIDERS[name] = provider_cls
