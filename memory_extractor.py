"""记忆提取模块 - 从对话中自动提取老人的个人信息。"""

import json
import os
from typing import Optional

from openai import OpenAI


EXTRACTION_PROMPT = """你是信息提取助手。请分析老人与AI助手的对话，提取关于老人的个人信息。

规则：
1. 只提取对话中**新出现**或**有变化**的信息
2. 如果某类信息已经存在于"已知信息"中且没有变化，不要重复提取
3. 返回严格的JSON格式，不要任何其他文字
4. 如果没有新信息，返回空对象 {{}}

已知信息：
{existing_profile}

【重要规则】
- 只从"老人说的话"中提取信息，AI回复中的内容可能不准确，不要参考
- 如果老人说的和已知信息有冲突，以老人说的为准
- 如果老人只是问问题而没有提供新信息，返回空对象

老人说的话：
{user_message}

请按以下结构提取新信息，返回JSON：
{{
  "name": "姓名（如果提到）",
  "age": "年龄（如果提到）",
  "city": "所在城市（如果提到）",
  "birthday": "生日（如果提到）",
  "hometown": "家乡（如果提到）",
  "family": {{
    "children": "子女情况",
    "grandchildren": "孙子孙女情况",
    "spouse": "配偶情况"
  }},
  "health": {{
    "chronic_conditions": ["慢性病列表"],
    "medications": "在吃什么药",
    "doctor_advice": "医生嘱咐"
  }},
  "interests": {{
    "tv_shows": "喜欢看的剧/节目",
    "hobbies": ["爱好1", "爱好2"],
    "pets": "宠物情况"
  }},
  "daily_routine": {{
    "wake_up": "起床时间",
    "favorite_food": "爱吃的食物",
    "sleep_time": "睡觉时间"
  }},
  "recent_events": {{
    "looking_forward_to": "最近期待的事",
    "worried_about": "最近担心的事",
    "other": "其他重要事件"
  }}
}}

只返回JSON，不要任何解释或markdown代码块。"""


class MemoryExtractor:
    """调用 LLM 从对话中提取结构化记忆。"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def extract(self, user_message: str, existing_profile: dict) -> dict:
        """分析老人的话，返回需要更新的画像字段。"""
        profile_text = json.dumps(existing_profile, ensure_ascii=False, indent=2)
        prompt = EXTRACTION_PROMPT.format(
            existing_profile=profile_text,
            user_message=user_message,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专门提取老人个人信息的信息抽取助手。只输出纯JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=512,
            )

            content = response.choices[0].message.content or "{}"
            content = content.strip()

            # 清理可能的 markdown 代码块
            if content.startswith("```"):
                lines = content.splitlines()
                # 去掉首行的 ```json 和尾行的 ```
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()

            return json.loads(content)
        except Exception:
            return {}

    def extract_sync(
        self, user_message: str, existing_profile: dict
    ) -> dict:
        """同步版本，供后台任务调用。"""
        return self.extract(user_message, existing_profile)
