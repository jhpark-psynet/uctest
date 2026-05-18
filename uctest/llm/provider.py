from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMConfig:
    temperature: float = 0.0
    max_tokens: int = 1000
    response_format: str = "text"   # "text" | "json"


@dataclass
class LLMResponse:
    text: str
    raw: dict | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        system: str,
        user: str,
        config: LLMConfig | None = None,
    ) -> LLMResponse: ...
