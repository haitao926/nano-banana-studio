from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, constr


class UserRegister(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


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


class BatchDownloadRequest(BaseModel):
    filenames: List[str]


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


class ModelCatalogItem(BaseModel):
    model: str
    label: Optional[str] = None
    service: Literal["image", "video", "audio", "digital_human", "prompt"]
    platform: Optional[str] = None
    api_key: Optional[str] = None
    backup_keys: List[str] = Field(default_factory=list)
    base_url: Optional[str] = None
    cost: Optional[int] = None
    enabled: bool = True


class SystemConfigUpdateRequest(BaseModel):
    image: SystemImageConfig
    tts: SystemTTSConfig
    video: Optional[SystemVideoConfig] = None
    key_pools: Optional[List[Dict]] = None
    models: Optional[List[ModelCatalogItem]] = None


class CropRequest(BaseModel):
    image_url: str
    crops: List[Dict[str, int]]  # [{x, y, w, h}, ...]
