"""安伴 - 全局配置文件，所有配置项从环境变量读取。"""

import os
from functools import lru_cache


class Settings:
    """应用配置，支持通过环境变量覆盖默认值。"""

    # FastAPI 服务
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

    # LLM 提供商选择（支持：kimi，后续可扩展）
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "kimi")

    # Kimi (Moonshot) API 配置
    KIMI_API_KEY: str = os.getenv("KIMI_API_KEY", "")
    KIMI_BASE_URL: str = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
    KIMI_MODEL: str = os.getenv("KIMI_MODEL", "moonshot-v1-8k")
    KIMI_TEMPERATURE: float = float(os.getenv("KIMI_TEMPERATURE", "0.7"))
    KIMI_MAX_TOKENS: int = int(os.getenv("KIMI_MAX_TOKENS", "512"))

    # 天气配置
    WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY", "")
    DEFAULT_CITY: str = os.getenv("DEFAULT_CITY", "北京")

    # 角色设定
    SYSTEM_PROMPT: str = os.getenv(
        "SYSTEM_PROMPT",
        (
            "你是小安，一个温暖贴心的AI陪伴助手，专门陪伴独居老人。\n"
            "说话风格：简洁、口语化、像家人一样亲切，不用复杂词汇。\n"
            "每次回复控制在3句话以内，让老人听起来不累。\n"
            "会主动关心老人的健康、饮食、心情。\n"
            "遇到健康问题会提醒老人注意，必要时建议联系子女或医生。\n"
            "如果老人提到身体不适，要表达关心并建议及时就医。\n"
            "多使用'您'，语气温柔有耐心。\n\n"
            "你的能力：\n"
            "1. 能查询天气，老人问天气时你会查完告诉TA\n"
            "2. 能解答各种生活常识、健康问题、历史人文、操作指导\n\n"
            "回答原则：\n"
            "- 用简单的话解释复杂的事，不用专业术语\n"
            "- 健康问题要谨慎，建议看医生，不给出具体用药建议\n"
            "- 操作指导一步一步慢慢说，不要太快\n"
            "- 天气回答要贴心：温度多少、穿什么、适不适合出门遛弯\n"
            "- 不确定的事诚实说'这个我不太确定'，让老人问子女或专业人士"
        ),
    )

    # 主动对话话题模板（预留，可被外部传入覆盖）
    PROACTIVE_TOPICS: list[str] = [
        "早安问候，关心老人昨晚睡得怎么样",
        "午饭提醒，问问老人今天吃了什么",
        "下午闲聊，聊聊天气或兴趣爱好",
        "晚餐提醒，提醒老人按时吃饭",
        "晚间关怀，问问今天过得开不开心",
    ]


def get_proactive_topic(index: int | None = None) -> str:
    """获取一个主动对话的话题。"""
    topics = Settings.PROACTIVE_TOPICS
    if index is not None and 0 <= index < len(topics):
        return topics[index]
    import random
    return random.choice(topics)


@lru_cache
def get_settings() -> Settings:
    """返回单例配置对象。"""
    return Settings()
