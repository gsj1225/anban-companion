"""LLM Provider 抽象基类，定义统一接口。"""

from abc import ABC, abstractmethod
from typing import Iterable


class ChatMessage(dict):
    """单条聊天消息，兼容 OpenAI 消息格式。

    Example:
        >>> msg = ChatMessage(role="user", content="你好")
        >>> msg
        {'role': 'user', 'content': '你好'}
    """

    def __init__(self, role: str, content: str):
        super().__init__(role=role, content=content)
        self.role = role
        self.content = content


class LLMProvider(ABC):
    """LLM 提供商抽象基类。

    所有新增的大模型接入都必须继承此类，并实现 `call` 方法。
    业务代码（main.py）只依赖此接口，实现零改动切换模型。
    """

    @abstractmethod
    def call(
        self,
        chat_history: Iterable[ChatMessage],
        system_prompt: str,
    ) -> str:
        """调用大模型，返回文本回复。

        Args:
            chat_history: 历史对话消息列表，按时间顺序排列。
            system_prompt: 系统提示词（角色设定）。

        Returns:
            模型生成的回复文本。
        """
        ...
