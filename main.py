"""安伴 - 老人陪伴AI对话服务主入口（集成记忆功能）。"""

import asyncio
import os
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import edge_tts
from fastapi import BackgroundTasks, FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    RateLimitError,
)
from pydantic import BaseModel, Field
from typing import List

from config import get_settings, get_proactive_topic
from providers import get_provider
from providers.base import ChatMessage
from user_profile import load_profile, save_profile, merge_profile, format_profile_for_prompt
from memory_extractor import MemoryExtractor
from chat_history import load_history, load_llm_context, save_message, clear_history
from weather import (
    is_weather_query,
    get_weather,
    format_weather_for_prompt,
    extract_city_from_text,
)


# 修复 torch / numpy OpenMP 冲突
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# 把 imageio-ffmpeg 的 ffmpeg 加入 PATH，供 Whisper 调用
import imageio_ffmpeg
_ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
_ffmpeg_dir = os.path.dirname(_ffmpeg_exe)
_current_path = os.environ.get("PATH", "")
os.environ["PATH"] = _ffmpeg_dir + os.pathsep + _current_path


# ---------------------------------------------------------------------------
# 应用生命周期
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化所有组件。"""
    settings = get_settings()
    app.state.provider = get_provider(settings.LLM_PROVIDER)
    app.state.system_prompt = settings.SYSTEM_PROMPT

    # 初始化记忆提取器（复用 Kimi API 配置）
    app.state.memory_extractor = MemoryExtractor(
        api_key=settings.KIMI_API_KEY or os.getenv("KIMI_API_KEY", ""),
        base_url=settings.KIMI_BASE_URL,
        model=settings.KIMI_MODEL,
    )

    # 加载 Whisper 语音识别模型
    import whisper
    app.state.whisper_model = whisper.load_model("tiny")
    app.state.executor = ThreadPoolExecutor(max_workers=2)

    yield

    app.state.executor.shutdown(wait=False)


app = FastAPI(
    title="安伴 - 老人陪伴AI对话服务",
    description="像家人一样陪伴独居老人的AI对话系统",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """用户发送消息的请求体。"""
    user_id: str = Field(default="default", description="用户标识")
    user_message: str = Field(..., description="老人输入的消息", min_length=1)
    # history 字段保留兼容，但后端优先使用持久化存储的历史记录


class ChatResponse(BaseModel):
    """AI 回复的响应体。"""
    reply: str = Field(..., description="小安的回复")
    success: bool = Field(True, description="是否成功")


class ProactiveRequest(BaseModel):
    """主动发起对话的请求体。"""
    user_id: str = Field(default="default", description="用户标识")
    topic: str | None = Field(None, description="主动对话话题")


class ProactiveResponse(BaseModel):
    """主动发起对话的响应体。"""
    greeting: str = Field(..., description="小安主动发起的话")
    topic: str = Field(..., description="本次话题")
    success: bool = Field(True, description="是否成功")


class TTSRequest(BaseModel):
    """语音合成请求体。"""
    text: str = Field(..., description="要朗读的文本", min_length=1)
    voice: str = Field(default="zh-CN-XiaoxiaoNeural", description="音色代码")
    rate: float = Field(default=1.0, description="语速倍率，0.5-2.0", ge=0.5, le=2.0)
    volume: float = Field(default=1.0, description="音量倍率，0.5-1.5", ge=0.5, le=1.5)


class ASRResponse(BaseModel):
    """语音识别响应体。"""
    text: str = Field(..., description="识别出的文字")
    success: bool = Field(True, description="是否成功")


class ProfileUpdateRequest(BaseModel):
    """手动更新用户画像的请求体。"""
    profile: dict = Field(..., description="完整的用户画像JSON")


DEFAULT_TTS_VOICE = "zh-CN-XiaoxiaoNeural"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return "小安的连接出了点问题，可能需要联系家人帮忙看看哦。"
    if isinstance(exc, RateLimitError):
        return "小安暂时有点累，请您稍等一会儿再试，好吗？"
    if isinstance(exc, APIConnectionError):
        return "网络好像不太稳，小安没听清，您能再说一遍吗？"
    if isinstance(exc, APIError):
        return "小安刚才走神了，您能再说一遍吗？"
    return "小安这里出了点小状况，您稍等一下再试试，好吗？"


def _build_system_prompt(base_prompt: str, profile: dict) -> str:
    """把用户画像注入 system prompt。"""
    profile_text = format_profile_for_prompt(profile)
    memory_hint = (
        "\n\n【关于这位老人】\n"
        f"{profile_text}\n\n"
        "请记住TA告诉过你的事，像认识很久的朋友一样聊天。"
        "如果提到已知信息，可以自然地说'我记得您之前说过...'。"
        "不要反复问同样的问题，如果已经知道就不要再问。"
    )
    return base_prompt + memory_hint


# ---------------------------------------------------------------------------
# 后台任务：提取记忆
# ---------------------------------------------------------------------------

def _extract_memory_task(user_id: str, user_message: str):
    """在后台线程中提取记忆并更新用户画像。"""
    try:
        profile = load_profile(user_id)
        extractor = app.state.memory_extractor
        new_info = extractor.extract_sync(user_message, profile)
        if new_info:
            updated = merge_profile(profile, new_info)
            save_profile(user_id, updated)
    except Exception:
        pass  # 记忆提取失败不影响主流程


# ---------------------------------------------------------------------------
# API 路由
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse, summary="对话接口")
async def chat(req: ChatRequest, background_tasks: BackgroundTasks) -> ChatResponse:
    """接收老人消息，结合记忆返回小安的回复。"""
    provider = app.state.provider
    profile = load_profile(req.user_id)

    # ---------- 天气查询检测 ----------
    weather_hint = ""
    if is_weather_query(req.user_message):
        city = extract_city_from_text(req.user_message)
        if city and not profile.get("city"):
            profile["city"] = city
            save_profile(req.user_id, profile)
        if not city:
            city = profile.get("city") or get_settings().DEFAULT_CITY
        weather_data = get_weather(city)
        weather_hint = "\n\n" + format_weather_for_prompt(weather_data)

    system_prompt = _build_system_prompt(app.state.system_prompt, profile) + weather_hint

    # 从持久化存储加载历史记录作为 LLM 上下文
    context = load_llm_context(req.user_id)
    chat_history = [ChatMessage(m["role"], m["content"]) for m in context]
    chat_history.append(ChatMessage("user", req.user_message))

    try:
        reply = provider.call(chat_history, system_prompt)
        # 保存对话到持久化存储
        save_message(req.user_id, "user", req.user_message)
        save_message(req.user_id, "assistant", reply)
        # 异步提取记忆（只从老人说的话中提取），不阻塞响应
        background_tasks.add_task(
            _extract_memory_task, req.user_id, req.user_message
        )
        return ChatResponse(reply=reply)
    except Exception as exc:
        return ChatResponse(reply=_friendly_error(exc), success=False)


@app.post("/proactive", response_model=ProactiveResponse, summary="主动发起对话")
async def proactive(req: ProactiveRequest | None = None) -> ProactiveResponse:
    """主动发起对话接口。"""
    provider = app.state.provider
    user_id = req.user_id if req else "default"
    profile = load_profile(user_id)
    system_prompt = _build_system_prompt(app.state.system_prompt, profile)

    topic = (req.topic if req else None) or get_proactive_topic()
    proactive_system = (
        f"{system_prompt}\n"
        f"【本次任务】现在是主动关怀时间，话题是：{topic}\n"
        f"请用温暖自然的口吻开头，不要机械地打招呼。"
    )

    try:
        greeting = provider.call([], proactive_system)
        return ProactiveResponse(greeting=greeting, topic=topic)
    except Exception as exc:
        return ProactiveResponse(
            greeting=_friendly_error(exc), topic=topic, success=False
        )


def _fmt_percent(val: float) -> str:
    """把 0.5~2.0 倍率转成 edge-tts 的 +/-N% 格式。"""
    pct = int((val - 1.0) * 100)
    return f"{pct:+d}%"


@app.post("/tts", summary="语音合成")
async def tts(req: TTSRequest, background_tasks: BackgroundTasks) -> FileResponse:
    """把文字转成语音，返回 MP3 音频文件。"""
    voice = req.voice or DEFAULT_TTS_VOICE
    rate_str = _fmt_percent(req.rate)
    volume_str = _fmt_percent(req.volume)
    communicate = edge_tts.Communicate(
        req.text, voice=voice, rate=rate_str, volume=volume_str
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_path = tmp.name

    await communicate.save(tmp_path)
    background_tasks.add_task(os.remove, tmp_path)

    return FileResponse(tmp_path, media_type="audio/mpeg")


@app.post("/asr", response_model=ASRResponse, summary="语音识别")
async def asr(audio: UploadFile = File(...)) -> ASRResponse:
    """接收音频文件，返回识别出的文字。"""
    suffix = os.path.splitext(audio.filename or ".webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        content = await audio.read()
        tmp.write(content)

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            app.state.executor,
            lambda: app.state.whisper_model.transcribe(
                tmp_path, language="zh", fp16=False
            ),
        )
        text = result["text"].strip()
        return ASRResponse(text=text)
    except Exception:
        traceback.print_exc()
        return ASRResponse(text="小安没听清，请您再说一遍好吗？", success=False)
    finally:
        os.remove(tmp_path)


@app.get("/user-profile/{user_id}", summary="查看用户画像")
async def get_user_profile(user_id: str) -> dict:
    """获取指定用户的画像信息。"""
    return load_profile(user_id)


@app.put("/user-profile/{user_id}", summary="更新用户画像")
async def update_user_profile(user_id: str, req: ProfileUpdateRequest) -> dict:
    """手动更新用户画像（会完全覆盖）。"""
    profile = req.profile
    profile["user_id"] = user_id
    save_profile(user_id, profile)
    return {"success": True, "message": "画像已更新", "profile": profile}


@app.get("/chat-history/{user_id}", summary="获取聊天记录")
async def get_chat_history(user_id: str) -> dict:
    """获取指定用户的聊天记录（最近200条）。"""
    messages = load_history(user_id)
    return {"user_id": user_id, "messages": messages}


@app.delete("/chat-history/{user_id}", summary="清空聊天记录")
async def delete_chat_history(user_id: str) -> dict:
    """清空指定用户的聊天记录。"""
    clear_history(user_id)
    return {"success": True, "message": "聊天记录已清空"}


@app.get("/health", summary="健康检查")
async def health() -> dict:
    return {"status": "ok", "service": "安伴"}


# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
