import os
from pathlib import Path

# Thư mục gốc
BASE_DIR = Path(__file__).parent.absolute()

# Database
DB_PATH = os.path.join(BASE_DIR, "data", "tts_eval.db")

# Thư mục audio
AUDIO_DIR = os.path.join(BASE_DIR, "static", "audio")

# Cài đặt bảo mật
SECRET_KEY = "your-secret-key-change-in-production"
SESSION_EXPIRY = 3600  # Thời gian hết hạn session (giây)
PASSWORD_SALT_LENGTH = 32

# MOS Attributes
MOS_ATTRIBUTES = [
    {"id": "naturalness", "label": "Tự nhiên", "description": "Giọng đọc nghe tự nhiên như người thật không?"},
    {"id": "intelligibility", "label": "Rõ ràng", "description": "Nội dung rõ ràng, dễ hiểu không?"},
    {"id": "pronunciation", "label": "Phát âm", "description": "Phát âm chính xác không?"},
    {"id": "prosody", "label": "Ngữ điệu", "description": "Ngữ điệu, nhịp điệu phù hợp không?"},
    #{"id": "speaker_similarity", "label": "Giống giọng người", "description": "Giống với giọng nói của người gốc không?"},
    {"id": "overall_rating", "label": "Tổng thể", "description": "Đánh giá tổng thể về chất lượng"}
]

# A/B Test Attributes (giống MOS attributes)
AB_TEST_ATTRIBUTES = MOS_ATTRIBUTES

# Audio models
MODELS = {
    "elevenlab": "ElevenLab",
    "vits": "VITS",
    "xtts": "XTTS"
}