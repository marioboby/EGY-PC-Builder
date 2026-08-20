from __future__ import annotations
from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """
    Abstract base for all LLM providers.
    Subclasses implement only _complete() — everything else is shared.
    """

    MODEL_NAME: str = ""

    @abstractmethod
    async def _complete(self, system: str, user_msg: str) -> str:
        """
        Send system + user message to the model, return raw text response.
        Each provider implements this differently.
        """
        ...
