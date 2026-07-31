from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ProviderModel:
    """
    存储每个模型提供商的调用参数信息，用于从数据库读取并动态构建 GPT 调用实例。
    """
    id: str                     # 模型唯一 ID（推荐用 UUID）
    logo: str                   # 模型图标 URL
    name: str                   # 展示名，如 "GPT-4 Turbo"（用于前端展示）
    api_key: str                # 调用该模型使用的 API Key
    base_url: str               # 模型 API 接口地址（OpenAI SDK兼容）
    created_at: Optional[datetime] = None  # 可选：创建时间（从 SQLite 自动生成）