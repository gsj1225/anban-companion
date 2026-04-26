# 安伴 - 老人陪伴AI对话服务

像家人一样陪伴独居老人的 AI 对话系统。日常称呼"小安"，温暖贴心、简洁亲切。

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# Linux / macOS
export KIMI_API_KEY="your-moonshot-api-key"

# Windows (CMD)
set KIMI_API_KEY=your-moonshot-api-key

# Windows (PowerShell)
$env:KIMI_API_KEY="your-moonshot-api-key"
```

可选环境变量：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `KIMI_API_KEY` | — | **必填**，Moonshot API 密钥 |
| `KIMI_BASE_URL` | `https://api.moonshot.cn/v1` | Kimi API 地址 |
| `KIMI_MODEL` | `moonshot-v1-8k` | 模型名称 |
| `KIMI_TEMPERATURE` | `0.7` | 生成温度 |
| `KIMI_MAX_TOKENS` | `512` | 最大生成长度 |
| `LLM_PROVIDER` | `kimi` | 提供商（当前仅支持 kimi） |
| `APP_HOST` | `0.0.0.0` | 服务绑定地址 |
| `APP_PORT` | `8000` | 服务端口 |

### 3. 启动服务

```bash
python main.py
```

服务启动后访问：http://localhost:8000/docs （自动生成的接口文档）

## 接口说明

### POST `/chat` — 对话

接收老人消息，返回小安回复。

**请求示例：**

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "今天天气不错，出去走了走",
    "history": []
  }'
```

**响应示例：**

```json
{
  "reply": "真好呀，出去活动活动对身体好。您走了多久？累不累？记得喝口水休息一下。",
  "success": true
}
```

### POST `/proactive` — 主动发起对话

供定时任务调用，小安主动关心老人。

```bash
# 随机话题
curl -X POST "http://localhost:8000/proactive" \
  -H "Content-Type: application/json" \
  -d '{}'

# 指定话题
curl -X POST "http://localhost:8000/proactive" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "提醒老人按时吃降压药"
  }'
```

**响应示例：**

```json
{
  "greeting": "阿姨，该吃药啦。降压药吃了吗？记得定个闹钟，别忘啦。",
  "topic": "提醒老人按时吃降压药",
  "success": true
}
```

### GET `/health` — 健康检查

```bash
curl "http://localhost:8000/health"
```

## 如何接入新的大模型

整个架构设计为"业务代码零改动"，新增模型只需 2 步：

### 第 1 步：实现 Provider

在 `providers/` 下新建文件，继承 `LLMProvider`，实现 `call` 方法。

**示例：接入 DeepSeek**

```python
# providers/deepseek.py
from typing import Iterable
from openai import OpenAI
from providers.base import LLMProvider, ChatMessage
from config import get_settings


class DeepSeekProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1",
        )
        self.model = settings.DEEPSEEK_MODEL

    def call(self, chat_history: Iterable[ChatMessage], system_prompt: str) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content or ""
```

### 第 2 步：注册到工厂

在 `providers/__init__.py` 的 `_PROVIDER_REGISTRY` 中加入新模型：

```python
from providers.deepseek import DeepSeekProvider

_PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "kimi": KimiProvider,
    "deepseek": DeepSeekProvider,   # <-- 新增
}
```

### 第 3 步：配置切换

通过环境变量切换模型，业务代码无需任何改动：

```bash
export LLM_PROVIDER="deepseek"
export DEEPSEEK_API_KEY="your-key"
export DEEPSEEK_MODEL="deepseek-chat"
python main.py
```

### 设计说明

- **`LLMProvider` 抽象基类**：定义统一的 `call(chat_history, system_prompt)` 接口
- **`get_provider` 工厂函数**：根据配置字符串返回对应实例，解耦业务代码与具体模型
- **`config.py`**：集中管理所有配置项，新增模型只需在 `Settings` 中加字段即可
