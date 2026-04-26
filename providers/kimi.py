"""Kimi (Moonshot AI) Provider 实现。"""

import os
from typing import Iterable

from openai import OpenAI

from providers.base import LLMProvider, ChatMessage
from config import get_settings


class KimiProvider(LLMProvider):
    """Kimi API 实现，使用 OpenAI 兼容接口。"""

    def __init__(self):
        settings = get_settings()
        api_key = settings.KIMI_API_KEY or os.getenv("KIMI_API_KEY")
        if not api_key:
            raise ValueError(
                "KIMI_API_KEY 未设置，请通过环境变量或 .env 文件配置。"
            )
        self.client = OpenAI(
            api_key=api_key,
            base_url=settings.KIMI_BASE_URL,
        )
        self.model = settings.KIMI_MODEL
        self.temperature = settings.KIMI_TEMPERATURE
        self.max_tokens = settings.KIMI_MAX_TOKENS

    def call(
        self,
        chat_history: Iterable[ChatMessage],
        system_prompt: str,
    ) -> str:
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        content = response.choices[0].message.content
        return content or ""
