"""LLM Provider 模块导出。"""

from providers.base import LLMProvider
from providers.kimi import KimiProvider

__all__ = ["LLMProvider", "KimiProvider", "get_provider"]


# 模型注册表：新增模型时，在这里注册即可
_PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "kimi": KimiProvider,
}


def get_provider(provider_name: str) -> LLMProvider:
    """工厂函数：根据名称返回对应的 Provider 实例。

    Args:
        provider_name: 配置中的 LLM_PROVIDER 值。

    Returns:
        LLMProvider 实例。

    Raises:
        ValueError: 找不到对应的 Provider。
    """
    provider_cls = _PROVIDER_REGISTRY.get(provider_name)
    if provider_cls is None:
        supported = ", ".join(_PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"不支持的 LLM 提供商: '{provider_name}'。"
            f"当前支持: {supported}"
        )
    return provider_cls()
