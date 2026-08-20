from __future__ import annotations
import os

from google import genai
from google.genai import types

from .base import BaseLLM


# ── Claude (Anthropic) ─────────────────────────────────────────────────────────

class ClaudeLLM(BaseLLM):
    MODEL_NAME = "claude-sonnet-4-5"

    def __init__(self, model: str = MODEL_NAME):
        import anthropic
        self.model  = model
        self.client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY

    async def _complete(self, system: str, user_msg: str) -> str:
        response = await self.client.messages.create(
            model      = self.model,
            max_tokens = 4096,
            system     = system,
            messages   = [{"role": "user", "content": user_msg}],
        )
        return response.content[0].text


# ── GPT (OpenAI) ───────────────────────────────────────────────────────────────

class GPT(BaseLLM):
    MODEL_NAME = "gpt-4o"

    def __init__(self, model: str = MODEL_NAME):
        from openai import AsyncOpenAI
        self.model  = model
        self.client = AsyncOpenAI(api_key=os.getenv("GPT_API_KEY"))

    async def _complete(self, system: str, user_msg: str) -> str:
        response = await self.client.chat.completions.create(
            model      = self.model,
            max_tokens = 4096,
            messages   = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
        )
        return response.choices[0].message.content


# ── Gemini (Google) ────────────────────────────────────────────────────────────

class GeminiLLM(BaseLLM):
    MODEL_NAME = "gemini-3.5-flash"

    def __init__(self, model: str = MODEL_NAME):
        self.model_name = model
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def __del__(self):
        self.client.close()

    async def _complete(self, system: str, user_msg: str) -> str:
        chat = self.client.aio.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                system_instruction=system
            ),
        )
        response = await chat.send_message(user_msg)
        return response.text


# ── Local model via Ollama ─────────────────────────────────────────────────────

class OllamaLLM(BaseLLM):
    """
    Runs any local model through Ollama (ollama.com).
    Install Ollama, then: ollama pull llama3 / mistral / deepseek-r1 / etc.
    """
    MODEL_NAME = "llama3"

    def __init__(self, model: str = MODEL_NAME, base_url: str = "http://localhost:11434"):
        from openai import AsyncOpenAI
        self.model  = model
        # Ollama exposes an OpenAI-compatible API — no extra SDK needed
        self.client = AsyncOpenAI(
            api_key  = "ollama",   # required but ignored by Ollama
            base_url = f"{base_url}/v1",
        )

    async def _complete(self, system: str, user_msg: str) -> str:
        response = await self.client.chat.completions.create(
            model    = self.model,
            messages = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
        )
        return response.choices[0].message.content


# ── Factory ────────────────────────────────────────────────────────────────────

def get_llm(provider: str = "gemini", model: str | None = None) -> BaseLLM:
    """
    Instantiate the right LLM from a string — used in main.py and routes.
    Provider is read from LLM_PROVIDER env var if not passed directly.

    Examples:
        get_llm("claude")
        get_llm("gpt",    model="gpt-4-turbo")
        get_llm("gemini", model="gemini-1.5-flash")
        get_llm("ollama", model="mistral")
    """
    provider = provider or os.getenv("LLM_PROVIDER", "gemini")

    providers = {
        "claude": ClaudeLLM,
        "gpt":    GPT,
        "gemini": GeminiLLM,
        "ollama": OllamaLLM,
    }

    if provider not in providers:
        raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(providers)}")

    cls = providers[provider]
    return cls(model) if model else cls()
