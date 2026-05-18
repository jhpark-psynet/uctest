import pytest

from uctest.llm.provider import LLMConfig, LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    def __init__(
        self,
        response_text: str = "mock response",
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        **kwargs,
    ):
        self.response_text = response_text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.calls: list[dict] = []

    async def generate(self, system: str, user: str, config: LLMConfig | None = None) -> LLMResponse:
        self.calls.append({"system": system, "user": user, "config": config})
        return LLMResponse(
            text=self.response_text,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


@pytest.fixture
def mock_llm_json():
    return MockLLMProvider('{"label": "in_match", "confidence": 0.95}')


@pytest.fixture
def mock_llm_yes():
    return MockLLMProvider("yes")
