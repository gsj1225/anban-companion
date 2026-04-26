"""聊天记录持久化存储模块。"""

import json
import os
from datetime import datetime
from typing import List

CHAT_DIR = os.path.join(os.path.dirname(__file__), "data", "chat_history")
os.makedirs(CHAT_DIR, exist_ok=True)

# 每个用户最多保存的消息条数
MAX_HISTORY = 200
# 传给 LLM 的最近消息条数
LLM_CONTEXT_LIMIT = 20


def _history_path(user_id: str) -> str:
    return os.path.join(CHAT_DIR, f"{user_id}.json")


def load_history(user_id: str, limit: int = MAX_HISTORY) -> List[dict]:
    """加载用户的聊天记录。"""
    path = _history_path(user_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        messages = data.get("messages", [])
        return messages[-limit:] if len(messages) > limit else messages
    except Exception:
        return []


def load_llm_context(user_id: str, limit: int = LLM_CONTEXT_LIMIT) -> List[dict]:
    """加载用于 LLM 上下文的最近消息（去掉时间戳）。"""
    messages = load_history(user_id, limit=limit)
    return [{"role": m["role"], "content": m["content"]} for m in messages]


def save_message(user_id: str, role: str, content: str) -> None:
    """追加一条消息到历史记录。"""
    path = _history_path(user_id)
    data = {"user_id": user_id, "messages": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    messages = data.get("messages", [])
    messages.append({
        "timestamp": datetime.now().isoformat(),
        "role": role,
        "content": content,
    })

    # 只保留最近 MAX_HISTORY 条
    if len(messages) > MAX_HISTORY:
        messages = messages[-MAX_HISTORY:]

    data["messages"] = messages
    data["last_updated"] = datetime.now().isoformat()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clear_history(user_id: str) -> None:
    """清空用户聊天记录。"""
    path = _history_path(user_id)
    if os.path.exists(path):
        os.remove(path)
