from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, constr


class UserRegister(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    refresh_expires_in: Optional[int] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None


class CliDeviceApproveRequest(BaseModel):
    user_code: Optional[str] = None
    device_code: Optional[str] = None


class CliDevicePollRequest(BaseModel):
    device_code: str


class CliDeviceStartResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class CliDeviceSessionResponse(Token):
    base_url: str
    username: Optional[str] = None


class SingleGenRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "vivid"
    subject: str = "general"
    grade: str = "general"
    model: Optional[str] = None
    reference_image_url: Optional[str] = None
    reference_image_urls: List[str] = Field(default_factory=list)
    seedream_group: bool = False
    seedream_max_images: int = 4


class ModifyGenRequest(BaseModel):
    prompt: str
    original_image_url: str


class OptimizePromptRequest(BaseModel):
    prompt: str
    subject: str = "general"
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    channel: Optional[Literal["google", "bytedance", "aliyun", "byte"]] = None


class ClipRenderRequest(BaseModel):
    config: Dict


class ToggleFeatureRequest(BaseModel):
    filename: str
    featured: bool


class UserUpdateRequest(BaseModel):
    user_id: int
    is_pro: bool
    quota_limit: int


class AdminCreateUserRequest(BaseModel):
    username: constr(min_length=2, max_length=32)
    password: constr(min_length=6, max_length=64)
    is_pro: bool = False
    quota_limit: Optional[int] = None


class AdminBulkCreateUserItem(BaseModel):
    username: constr(min_length=2, max_length=32)
    password: constr(min_length=6, max_length=64)
    is_pro: bool = False
    quota_limit: Optional[int] = None


class AdminBulkCreateUsersRequest(BaseModel):
    users: List[AdminBulkCreateUserItem] = Field(default_factory=list, min_length=1, max_length=500)
    skip_existing: bool = True


class AssistantHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: constr(min_length=1, max_length=20000)


class BatchDownloadRequest(BaseModel):
    filenames: List[str]
    items: List[Dict] = Field(default_factory=list)


class BatchGenRequest(BaseModel):
    system_keys: List[str] = Field(default_factory=list)
    requirement_indices: List[int] = Field(default_factory=list)
    model: Optional[str] = None
    optimize: bool = False


class DigitalHumanRequest(BaseModel):
    image_url: str
    audio_url: str
    audio_duration: Optional[float] = None
    prompt: Optional[constr(max_length=300)] = None
    model: Optional[str] = None
    seed: int = -1
    resolution: Literal[480, 720, 1080] = 480
    fast_mode: bool = False
    style: Optional[constr(max_length=30)] = None


class VideoGenerateRequest(BaseModel):
    mode: Literal["text", "image"]
    prompt: constr(min_length=1, max_length=2000)
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    duration_seconds: Optional[int] = None
    image_url: Optional[str] = None
    images: Optional[List[str]] = None


class TTSRequest(BaseModel):
    text: constr(min_length=1, max_length=5000)
    voice: str = "Cherry"
    model: Optional[str] = None
    language_type: str = "Auto"
    instructions: Optional[constr(max_length=1600)] = None
    optimize_instructions: bool = True
    response_format: Literal["wav", "pcm"] = "wav"
    sample_rate: Literal[8000, 16000, 24000, 48000] = 24000
    mode: Literal["server_commit", "commit"] = "server_commit"


class SystemImageConfig(BaseModel):
    api_key: str = ""
    backup_keys: List[str] = Field(default_factory=list)
    base_url: Optional[str] = None


class SystemTTSConfig(BaseModel):
    api_key: str = ""
    backup_keys: List[str] = Field(default_factory=list)
    base_url: Optional[str] = None


class SystemVideoConfig(BaseModel):
    api_key: str = ""
    backup_keys: List[str] = Field(default_factory=list)
    base_url: Optional[str] = None


class CredentialConfig(BaseModel):
    id: Optional[str] = None
    label: str = ""
    scope: Literal["system", "personal"] = "system"
    service: Literal["image", "video", "audio", "digital_human", "prompt"] = "image"
    provider: Optional[str] = None
    base_url: Optional[str] = None
    primary_secret: str = ""
    backup_secrets: List[str] = Field(default_factory=list)
    priority: Optional[int] = None
    enabled: bool = True


class ModelCatalogItem(BaseModel):
    model: str
    label: Optional[str] = None
    service: Literal["image", "video", "audio", "digital_human", "prompt"]
    provider: Optional[str] = None
    base_url: Optional[str] = None
    cost: Optional[int] = None
    enabled: bool = True
    recommended: bool = False
    allow_personal_override: bool = True
    credential_chain: List[str] = Field(default_factory=list)


class PromptChannelConfig(BaseModel):
    enabled: bool = True
    models: List[str] = Field(default_factory=list)


class SystemConfigUpdateRequest(BaseModel):
    image: Optional[SystemImageConfig] = None
    tts: Optional[SystemTTSConfig] = None
    video: Optional[SystemVideoConfig] = None
    personal_access_enabled: Optional[bool] = None
    key_pools: Optional[List[Dict]] = None
    models: Optional[List[ModelCatalogItem]] = None
    model_catalog: Optional[List[ModelCatalogItem]] = None
    credentials: Optional[List[CredentialConfig]] = None
    prompt_channels: Optional[Dict[str, PromptChannelConfig]] = None


class CropRequest(BaseModel):
    image_url: str
    crops: List[Dict[str, int]]  # [{x, y, w, h}, ...]


class ModelTestRequest(BaseModel):
    service: Literal["image", "video", "audio", "digital_human", "prompt"]
    model: str
    platform: Optional[str] = None
    prompt: Optional[str] = None
    voice: Optional[str] = None
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    api_key: Optional[str] = None
    backup_keys: List[str] = Field(default_factory=list)
    base_url: Optional[str] = None
    resolution: Optional[str] = None
    duration_seconds: Optional[int] = None
    size: Optional[str] = None


class AssistantChatRequest(BaseModel):
    message: constr(min_length=1, max_length=20000)
    conversation_id: Optional[constr(min_length=4, max_length=64)] = None
    model: Optional[str] = None
    temperature: float = 0.6
    max_history_messages: int = Field(default=20, ge=4, le=100)
    file_ids: List[str] = Field(default_factory=list)
    history_messages: List[AssistantHistoryMessage] = Field(default_factory=list, max_length=100)
    system_prompt: Optional[str] = None
    enable_tools: bool = False
    max_tool_rounds: int = Field(default=4, ge=1, le=10)
