# PostgreSQL connection string
import os
from urllib.parse import urlparse
import streamlit as st

def get_db_url():
    import streamlit as st
    if 'postgres' in st.secrets:
    
        pg_config = st.secrets["postgres"]
        
        # Escape special characters in password
        password = pg_config.get('password', '').replace('@', '%40').replace('!', '%21')
        
        # Tạo URL string
        return f"postgresql://{pg_config.get('user')}:{password}@{pg_config.get('host')}:{pg_config.get('port')}/{pg_config.get('dbname')}"
    else:
        return os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/tts_evaluation_db')
    
DB_URL = get_db_url() 
AUDIO_DIR = os.path.join("static", "audio")

# Thông số đánh giá MOS
MOS_ATTRIBUTES = [
    {'id': 'naturalness', 'label': 'Naturalness', 'description': 'How natural does the voice sound?'},
    {'id': 'intelligibility', 'label': 'Intelligibility', 'description': 'How clear and understandable is the speech?'},
    {'id': 'pronunciation', 'label': 'Pronunciation', 'description': 'How accurate is the pronunciation?'},
    {'id': 'prosody', 'label': 'Prosody', 'description': 'How natural is the rhythm, stress, and intonation?'},
    {'id': 'overall_rating', 'label': 'Overall', 'description': 'Overall quality rating'}
]
MODELS = {
    "elevenlab": "ElevenLab",
    "vits": "VITS",
    "xtts": "XTTS",
    "f5tts": "F5TTS"
}