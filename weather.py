"""天气查询模块 - 支持和风天气（QWeather）API。"""

import hashlib
import os
from typing import Optional

import requests

# 常用城市编码缓存（和风天气 Location ID）
# 数据来自和风天气标准城市编码表
_COMMON_CITY_IDS = {
    "北京": "101010100",
    "上海": "101020100",
    "天津": "101030100",
    "重庆": "101040100",
    "哈尔滨": "101050101",
    "长春": "101060101",
    "沈阳": "101070101",
    "呼和浩特": "101080101",
    "石家庄": "101090101",
    "太原": "101100101",
    "西安": "101110101",
    "济南": "101120101",
    "乌鲁木齐": "101130101",
    "拉萨": "101140101",
    "西宁": "101150101",
    "兰州": "101160101",
    "银川": "101170101",
    "郑州": "101180101",
    "南京": "101190101",
    "武汉": "101200101",
    "杭州": "101210101",
    "合肥": "101220101",
    "福州": "101230101",
    "南昌": "101240101",
    "长沙": "101250101",
    "贵阳": "101260101",
    "成都": "101270101",
    "昆明": "101290101",
    "南宁": "101300101",
    "海口": "101310101",
    "广州": "101280101",
    "深圳": "101280601",
    "苏州": "101190401",
    "宁波": "101210401",
    "青岛": "101120201",
    "无锡": "101190201",
    "佛山": "101280800",
    "东莞": "101281601",
    "厦门": "101230201",
    "大连": "101070201",
    "温州": "101210701",
}

# 天气状况代码 -> 中文描述（备用映射）
_WEATHER_CODE_MAP = {
    "100": "晴", "101": "多云", "102": "少云", "103": "晴间多云", "104": "阴",
    "150": "晴", "151": "多云", "152": "少云", "153": "晴间多云", "154": "阴",
    "300": "阵雨", "301": "强阵雨", "302": "雷阵雨", "303": "强雷阵雨",
    "304": "雷阵雨伴有冰雹", "305": "小雨", "306": "中雨", "307": "大雨",
    "308": "极端降雨", "309": "毛毛雨", "310": "暴雨", "311": "大暴雨",
    "312": "特大暴雨", "313": "冻雨", "314": "小到中雨", "315": "中到大雨",
    "316": "大到暴雨", "317": "暴雨到大暴雨", "318": "大暴雨到特大暴雨",
    "350": "阵雨", "351": "强阵雨", "399": "雨",
    "400": "小雪", "401": "中雪", "402": "大雪", "403": "暴雪",
    "404": "雨夹雪", "405": "雨雪天气", "406": "雨夹雪", "407": "阵雪",
    "408": "小到中雪", "409": "中到大雪", "410": "大到暴雪", "499": "雪",
    "500": "薄雾", "501": "雾", "502": "霾", "503": "扬沙", "504": "浮尘",
    "507": "沙尘暴", "508": "强沙尘暴", "509": "浓雾", "510": "强浓雾",
    "511": "中度霾", "512": "重度霾", "513": "严重霾", "514": "大雾",
    "515": "特强浓雾", "800": "热", "801": "冷", "802": "舒适",
    "900": "未知", "999": "未知",
}


def _get_city_id(city: str, api_key: str) -> Optional[str]:
    """获取城市编码，优先查缓存，否则调 API 搜索。"""
    # 去掉常见后缀匹配
    city_clean = city.replace("市", "").replace("县", "").strip()
    for name, cid in _COMMON_CITY_IDS.items():
        if name == city_clean or name == city:
            return cid

    if not api_key:
        return None

    # 调城市搜索 API
    try:
        url = "https://geoapi.qweather.com/v2/city/lookup"
        resp = requests.get(
            url,
            params={"location": city_clean, "key": api_key, "range": "cn"},
            timeout=5,
        )
        data = resp.json()
        if data.get("code") == "200" and data.get("location"):
            return data["location"][0]["id"]
    except Exception:
        pass
    return None


def get_weather(city: str) -> dict:
    """查询指定城市的天气。

    Returns:
        {
            "city": "北京",
            "temp": "25",
            "condition": "晴",
            "suggestion": "适合出门活动",
            "forecast": [
                {"date": "今天", "temp_high": "28", "temp_low": "18", "condition": "晴"},
                {"date": "明天", ...},
            ],
            "source": "api" | "mock",
        }
    """
    api_key = os.getenv("WEATHER_API_KEY", "")

    # 没有 API key 时返回模拟数据，便于本地测试
    if not api_key:
        return _mock_weather(city)

    city_id = _get_city_id(city, api_key)
    if not city_id:
        return _mock_weather(city)

    try:
        # 实时天气
        now_url = "https://devapi.qweather.com/v7/weather/now"
        now_resp = requests.get(
            now_url, params={"location": city_id, "key": api_key}, timeout=5
        )
        now_data = now_resp.json()

        # 3 天预报
        fc_url = "https://devapi.qweather.com/v7/weather/3d"
        fc_resp = requests.get(
            fc_url, params={"location": city_id, "key": api_key}, timeout=5
        )
        fc_data = fc_resp.json()

        if now_data.get("code") != "200":
            return _mock_weather(city)

        now = now_data.get("now", {})
        temp = now.get("temp", "?")
        code = now.get("icon", "999")
        condition = now.get("text") or _WEATHER_CODE_MAP.get(str(code), "未知")

        # 预报数据
        forecast = []
        if fc_data.get("code") == "200" and fc_data.get("daily"):
            date_labels = ["今天", "明天", "后天"]
            for idx, day in enumerate(fc_data["daily"][:3]):
                forecast.append(
                    {
                        "date": date_labels[idx] if idx < len(date_labels) else day.get("fxDate", ""),
                        "temp_high": day.get("tempMax", "?"),
                        "temp_low": day.get("tempMin", "?"),
                        "condition": day.get("textDay", "未知"),
                    }
                )

        suggestion = _make_suggestion(
            int(temp) if temp != "?" else 20, condition
        )

        return {
            "city": city,
            "temp": temp,
            "condition": condition,
            "suggestion": suggestion,
            "forecast": forecast,
            "source": "api",
        }
    except Exception:
        # 任何异常都降级到模拟数据，保证服务可用
        return _mock_weather(city)


def _mock_weather(city: str) -> dict:
    """基于城市名生成稳定的模拟天气数据（用于测试或 API 不可用）。"""
    # 用城市名哈希生成稳定但看起来随机的数据
    h = int(hashlib.md5(city.encode("utf-8")).hexdigest(), 16)
    conditions = ["晴", "多云", "阴", "小雨", "多云"]
    condition = conditions[h % len(conditions)]
    base_temp = 15 + (h % 15)  # 15 ~ 29 度
    return {
        "city": city,
        "temp": str(base_temp),
        "condition": condition,
        "suggestion": _make_suggestion(base_temp, condition),
        "forecast": [
            {
                "date": "今天",
                "temp_high": str(base_temp + 2),
                "temp_low": str(base_temp - 2),
                "condition": condition,
            },
            {
                "date": "明天",
                "temp_high": str(base_temp + 1),
                "temp_low": str(base_temp - 3),
                "condition": conditions[(h + 1) % len(conditions)],
            },
            {
                "date": "后天",
                "temp_high": str(base_temp + 3),
                "temp_low": str(base_temp - 1),
                "condition": conditions[(h + 2) % len(conditions)],
            },
        ],
        "source": "mock",
    }


def _make_suggestion(temp: int, condition: str) -> str:
    """根据温度和天气生成老人能听懂的建议。"""
    parts = []
    if temp < 5:
        parts.append("今天很冷，要穿厚羽绒服，最好戴上围巾手套")
    elif temp < 12:
        parts.append("有点凉，建议穿毛衣加外套")
    elif temp < 20:
        parts.append("温度适中，穿件薄外套比较合适")
    elif temp < 28:
        parts.append("天气暖和，穿短袖或薄长袖都可以")
    else:
        parts.append("今天比较热，穿轻薄透气的衣服，注意多喝水")

    if "雨" in condition:
        parts.append("外面在下雨，出门记得带伞，路面滑要小心")
    elif "雪" in condition:
        parts.append("有雪，出门要注意防滑")
    elif condition in ("晴", "少云"):
        if temp >= 15:
            parts.append("阳光不错，适合出门遛弯")
        else:
            parts.append("虽然晴天但气温低，出门多穿点")
    elif "霾" in condition or "雾" in condition or condition in ("霾", "雾", "薄雾"):
        parts.append("空气质量不太好，出门建议戴口罩，减少户外运动")
    else:
        parts.append("可以正常出门活动")

    return "；".join(parts)


# 常见城市列表，供消息中提取城市名使用
_ALL_CITY_NAMES = list(_COMMON_CITY_IDS.keys())


def extract_city_from_text(text: str) -> Optional[str]:
    """从用户消息中提取提到的城市名。"""
    # 先匹配完整城市名（含"市"后缀）
    for city in _ALL_CITY_NAMES:
        if city in text or (city + "市") in text:
            return city
    return None


def is_weather_query(text: str) -> bool:
    """检测用户消息是否是天气查询意图。"""
    text = text.lower()
    # 强触发词（单独出现即可判定）
    strong = [
        "天气", "冷不冷", "热不热", "温度", "气温", "几度", "多少度",
        "带伞", "防晒", "穿衣", "穿啥", "穿什么",
    ]
    if any(kw in text for kw in strong):
        return True

    # 天气现象词
    phenoms = ["下雨", "下雪", "刮风", "风大", "雾霾", "大雾", "霾", "雷阵雨"]
    if any(kw in text for kw in phenoms):
        return True

    # 弱触发词 + 动作词组合（如"今天能出门吗"）
    weak = ["冷不", "热不", "凉", "暖", "湿"]
    action = ["出门", "遛弯", "散步", "活动", "出去", "逛街"]
    if any(w in text for w in weak) and any(a in text for a in action):
        return True

    return False


def format_weather_for_prompt(weather: dict) -> str:
    """把天气数据格式化成适合注入 LLM system prompt 的文字。"""
    lines = [
        f"【实时天气】{weather['city']}今天{weather['condition']}，{weather['temp']}度。",
        f"【建议】{weather['suggestion']}。",
    ]
    if weather.get("forecast") and len(weather["forecast"]) > 1:
        tomorrow = weather["forecast"][1]
        lines.append(
            f"【明天预报】{tomorrow['condition']}，最高{tomorrow['temp_high']}度，最低{tomorrow['temp_low']}度。"
        )
    return "\n".join(lines)
