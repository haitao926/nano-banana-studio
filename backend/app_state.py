import os
import sys

from core.env_utils import load_env_file
from core.image_generator import ImageGenerator
from core.batch_image_generator import BatchImageGenerator
from core.digital_human import DigitalHumanGenerator
from core.video_generator import VideoGenerator
from core.db_manager import DBManager
from core.rate_limiter import RateLimiter

# Ensure core imports are available
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load .env.nbs if present (do not override existing env)
if not getattr(sys, "frozen", False):
    load_env_file(os.path.join(BASE_DIR, "..", ".env.nbs"))

# --- Basic config ---
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin888")

# --- Path config ---
if getattr(sys, "frozen", False):
    BUNDLE_DIR = sys._MEIPASS
    EXEC_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = BASE_DIR
    EXEC_DIR = BUNDLE_DIR

if BUNDLE_DIR not in sys.path:
    sys.path.insert(0, BUNDLE_DIR)

STATIC_DIR = os.path.join(EXEC_DIR, "static")
GENERATED_DIR = os.path.join(STATIC_DIR, "generated")
BATCH_DIR = os.path.join(STATIC_DIR, "batch")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
AUDIO_DIR = os.path.join(STATIC_DIR, "audio")
CLIP_DIR = os.path.join(STATIC_DIR, "clips")

os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(BATCH_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(CLIP_DIR, exist_ok=True)

DATA_DIR = os.path.join(EXEC_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
SYSTEM_CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

# --- Core instances ---
img_gen = ImageGenerator()
batch_gen = BatchImageGenerator()
digital_human_gen = DigitalHumanGenerator()
video_gen = VideoGenerator()
db = DBManager(db_path=os.path.join(DATA_DIR, "app.db"))
rate_limiter = RateLimiter()

# --- Limits ---
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
UPLOAD_MAX_MB = int(os.getenv("UPLOAD_MAX_MB", "10"))
UPLOAD_MAX_BYTES = UPLOAD_MAX_MB * 1024 * 1024

UPLOAD_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
UPLOAD_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".webm"}
UPLOAD_AUDIO_EXTS = {".wav", ".mp3", ".aac", ".m4a", ".flac", ".ogg"}
UPLOAD_RATE_WINDOW_SEC = int(os.getenv("UPLOAD_RATE_WINDOW_SEC", "60"))
UPLOAD_RATE_MAX = int(os.getenv("UPLOAD_RATE_MAX", "30"))
MAX_BATCH_TASKS = int(os.getenv("BATCH_MAX_TASKS", "20"))
BATCH_WORKERS = int(os.getenv("BATCH_WORKERS", "2"))
BATCH_DELAY_SECONDS = float(os.getenv("BATCH_DELAY_SECONDS", "0"))
