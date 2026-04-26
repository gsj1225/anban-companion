"""用户画像管理模块 - 存储、加载、合并老人个人信息。"""

import json
import os
from datetime import datetime
from typing import Any

PROFILE_DIR = os.path.join(os.path.dirname(__file__), "profiles")
os.makedirs(PROFILE_DIR, exist_ok=True)


def _profile_path(user_id: str) -> str:
    return os.path.join(PROFILE_DIR, f"{user_id}.json")


def load_profile(user_id: str) -> dict:
    """加载用户画像，不存在则返回默认结构。"""
    path = _profile_path(user_id)
    if not os.path.exists(path):
        return _default_profile(user_id)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(user_id: str, profile: dict) -> None:
    """保存用户画像到 JSON 文件。"""
    profile["last_updated"] = datetime.now().isoformat()
    path = _profile_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def _default_profile(user_id: str) -> dict:
    """默认空画像结构。"""
    return {
        "user_id": user_id,
        "name": None,
        "age": None,
        "city": None,
        "birthday": None,
        "hometown": None,
        "family": {},
        "health": {},
        "interests": {},
        "daily_routine": {},
        "recent_events": {},
        "last_updated": datetime.now().isoformat(),
    }


def merge_profile(old: dict, new: dict, override_existing: bool = False) -> dict:
    """递归合并新信息到旧画像。

    Args:
        old: 现有画像
        new: 新提取的信息
        override_existing: 是否允许覆盖已有非空值。后台自动提取默认False（防幻觉污染），手动更新可传True
    """
    merged = old.copy()
    for key, value in new.items():
        if key in ("user_id", "last_updated"):
            continue
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_profile(merged[key], value, override_existing)
        elif value is not None and value != "" and value != []:
            old_value = merged.get(key)
            # 如果已有值且不为空，默认不覆盖（防止AI幻觉污染）
            if old_value is not None and old_value != "" and old_value != [] and not override_existing:
                continue
            merged[key] = value
    return merged


def format_profile_for_prompt(profile: dict) -> str:
    """把画像压缩成适合注入 system prompt 的简短文字。"""
    parts = []

    # 基础信息
    base = []
    if profile.get("name"):
        base.append(f"叫{profile['name']}")
    if profile.get("age"):
        base.append(f"{profile['age']}岁")
    if profile.get("hometown"):
        base.append(f"家乡是{profile['hometown']}")
    if base:
        parts.append("，".join(base))

    # 家庭
    family_parts = []
    f = profile.get("family", {})
    if f.get("children"):
        family_parts.append(f"子女：{f['children']}")
    if f.get("grandchildren"):
        family_parts.append(f"孙辈：{f['grandchildren']}")
    if f.get("spouse"):
        family_parts.append(f"配偶：{f['spouse']}")
    if family_parts:
        parts.append("；".join(family_parts))

    # 健康
    health_parts = []
    h = profile.get("health", {})
    if h.get("chronic_conditions"):
        health_parts.append(f"有{', '.join(h['chronic_conditions'])}")
    if h.get("medications"):
        health_parts.append(f"吃药：{h['medications']}")
    if h.get("doctor_advice"):
        health_parts.append(f"医嘱：{h['doctor_advice']}")
    if health_parts:
        parts.append("；".join(health_parts))

    # 兴趣
    interest_parts = []
    i = profile.get("interests", {})
    if i.get("tv_shows"):
        interest_parts.append(f"喜欢看{i['tv_shows']}")
    if i.get("hobbies"):
        interest_parts.append(f"爱好：{', '.join(i['hobbies'])}")
    if i.get("pets"):
        interest_parts.append(f"宠物：{i['pets']}")
    if interest_parts:
        parts.append("；".join(interest_parts))

    # 日常
    routine_parts = []
    r = profile.get("daily_routine", {})
    if r.get("wake_up"):
        routine_parts.append(f"{r['wake_up']}起床")
    if r.get("favorite_food"):
        routine_parts.append(f"爱吃{r['favorite_food']}")
    if r.get("sleep_time"):
        routine_parts.append(f"{r['sleep_time']}睡觉")
    if routine_parts:
        parts.append("；".join(routine_parts))

    # 近期
    recent_parts = []
    e = profile.get("recent_events", {})
    if e.get("looking_forward_to"):
        recent_parts.append(f"最近期待：{e['looking_forward_to']}")
    if e.get("worried_about"):
        recent_parts.append(f"最近担心：{e['worried_about']}")
    if e.get("other"):
        recent_parts.append(f"最近的事：{e['other']}")
    if recent_parts:
        parts.append("；".join(recent_parts))

    if not parts:
        return "（暂时不了解太多信息，请通过聊天慢慢了解TA）"

    return "关于这位老人：" + "；".join(parts) + "。"
