from abc import ABC, abstractmethod
from typing import  TypeVar

LLMResponse = TypeVar('LLMResponse')

class Agent(ABC):
    def __init__(self, api_key: str, helicone_api_key: str):
        self._api_key = api_key
        self._helicone_api_key = helicone_api_key

    @abstractmethod
    async def __call__(self, system_prompt: str, user_messages: list[dict], response_format: type[LLMResponse], helicone_headers: dict) -> LLMResponse | None:
        pass
