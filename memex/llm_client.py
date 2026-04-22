from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import anthropic
import openai


@dataclass
class LLMResponse:
    text: str


class LLMClient:
    def __init__(self, provider: str, model: str, base_url: Optional[str]) -> None:
        self.provider = provider
        self.model = model
        self.base_url = base_url

    def complete(self, prompt: str, max_tokens: int = 1024) -> LLMResponse:
        if self.provider == "anthropic":
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return LLMResponse(text=response.content[0].text)

        if self.provider in ("openai", "ollama"):
            client = openai.OpenAI(
                base_url=self.base_url,
                api_key=os.environ.get("OPENAI_API_KEY", "ollama"),  # env var for real OpenAI, fallback for local endpoints
            )
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return LLMResponse(text=response.choices[0].message.content)

        raise ValueError(f"Unknown provider: {self.provider!r}. Use 'anthropic', 'openai', or 'ollama'.")

    @classmethod
    def from_config(cls, config: object, stage: str) -> "LLMClient":
        """Create from a Config object. stage is 'flush' or 'compile'."""
        return cls(
            provider=getattr(config, f"{stage}_provider"),
            model=getattr(config, f"{stage}_model"),
            base_url=getattr(config, f"{stage}_base_url"),
        )
