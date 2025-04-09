import sqlite3
import os
import datetime

# Đảm bảo thư mục database tồn tại
if not os.path.exists('data'):
    os.makedirs('data')

# Tạo kết nối với database
conn = sqlite3.connect('data/tts_eval.db')
cursor = conn.cursor()

# Xóa các bảng nếu đã tồn tại
cursor.execute("DROP TABLE IF EXISTS mos_ratings")
cursor.execute("DROP TABLE IF EXISTS ab_tests")
cursor.execute("DROP TABLE IF EXISTS visualization_dashboard")
cursor.execute("DROP TABLE IF EXISTS users")
cursor.execute("DROP TABLE IF EXISTS samples")
cursor.execute("DROP TABLE IF EXISTS speakers")
cursor.execute("DROP TABLE IF EXISTS models")
cursor.execute("DROP TABLE IF EXISTS pairwise_comparisons")

# Tạo bảng models
cursor.execute('''
CREATE TABLE models (
    model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Tạo bảng speakers
cursor.execute('''
CREATE TABLE speakers (
    speaker_id INTEGER PRIMARY KEY AUTOINCREMENT,
    speaker_name TEXT NOT NULL,
    gender TEXT,
    age INTEGER,
    accent TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Tạo bảng samples với thêm trường speaker_id và vote_count
cursor.execute('''
CREATE TABLE samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER,
    speaker_id INTEGER,
    text TEXT NOT NULL,
    audio_url TEXT NOT NULL,
    language TEXT,
    is_ground_truth INTEGER DEFAULT 0,
    vote_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE CASCADE,
    FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE SET NULL
)
''')

# Tạo bảng users với thêm trường fullname
cursor.execute('''
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,     
    fullname TEXT,     
    password_hash TEXT NOT NULL,
    salt TEXT,
    is_admin INTEGER DEFAULT 0,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Tạo bảng mos_ratings
cursor.execute('''
CREATE TABLE mos_ratings (
    rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id INTEGER,
    user_id INTEGER,
    naturalness REAL CHECK (naturalness BETWEEN 1 AND 5),  
    intelligibility REAL CHECK (intelligibility BETWEEN 1 AND 5),  
    pronunciation REAL CHECK (pronunciation BETWEEN 1 AND 5),  
    prosody REAL CHECK (prosody BETWEEN 1 AND 5),  
    speaker_similarity REAL CHECK (speaker_similarity BETWEEN 1 AND 5),  
    overall_rating REAL CHECK (overall_rating BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_id) REFERENCES samples(sample_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
)
''')

# Tạo bảng ab_tests
cursor.execute('''
CREATE TABLE ab_tests (
    test_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_a_id INTEGER NOT NULL,
    sample_b_id INTEGER NOT NULL,
    user_id INTEGER,
    selected_sample TEXT CHECK (selected_sample IN ('A', 'B', 'tie')),
    selection_reason TEXT,
    test_duration INTEGER,  -- Thời gian hoàn thành đánh giá (giây)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_a_id) REFERENCES samples(sample_id) ON DELETE CASCADE,
    FOREIGN KEY (sample_b_id) REFERENCES samples(sample_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
)
''')


# Tạo bảng visualization_dashboard
cursor.execute('''
CREATE TABLE visualization_dashboard (
    dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    chart_type TEXT NOT NULL, -- 'bar', 'line', 'radar', 'heatmap', 'box_plot'
    data_source TEXT NOT NULL, -- SQL query hoặc reference tới view
    filter_criteria TEXT, -- JSON format của các bộ lọc
    axis_x TEXT, -- Trường dữ liệu cho trục X
    axis_y TEXT, -- Trường dữ liệu cho trục Y
    color_by TEXT, -- Trường dữ liệu phân nhóm màu
    created_by INTEGER,
    is_public BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
)
''')

# Tạo bảng pairwise_comparisons
cursor.execute('''
CREATE TABLE pairwise_comparisons (
    comparison_id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_name TEXT NOT NULL,
    test_description TEXT,
    model_a_id INTEGER NOT NULL,
    model_b_id INTEGER NOT NULL,
    total_votes INTEGER DEFAULT 0,
    model_a_wins INTEGER DEFAULT 0,
    model_b_wins INTEGER DEFAULT 0,
    tie_count INTEGER DEFAULT 0,
    preference_score REAL,
    p_value REAL,
    is_significant INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_a_id) REFERENCES models(model_id) ON DELETE CASCADE,
    FOREIGN KEY (model_b_id) REFERENCES models(model_id) ON DELETE CASCADE
)
''')

# Tạo chỉ mục để tối ưu truy vấn
cursor.execute("CREATE INDEX idx_samples_model_id ON samples(model_id)")
cursor.execute("CREATE INDEX idx_samples_speaker_id ON samples(speaker_id)")
cursor.execute("CREATE INDEX idx_samples_language ON samples(language)")
cursor.execute("CREATE INDEX idx_samples_vote_count ON samples(vote_count)")
cursor.execute("CREATE INDEX idx_mos_ratings_sample_id ON mos_ratings(sample_id)")
cursor.execute("CREATE INDEX idx_mos_ratings_user_id ON mos_ratings(user_id)")
cursor.execute("CREATE INDEX idx_ab_tests_sample_a_id ON ab_tests(sample_a_id)")
cursor.execute("CREATE INDEX idx_ab_tests_sample_b_id ON ab_tests(sample_b_id)")
cursor.execute("CREATE INDEX idx_ab_tests_user_id ON ab_tests(user_id)")
cursor.execute("CREATE INDEX idx_visualization_chart_type ON visualization_dashboard(chart_type)")
cursor.execute("CREATE INDEX idx_visualization_is_public ON visualization_dashboard(is_public)")
cursor.execute("CREATE INDEX idx_pairwise_model_a ON pairwise_comparisons(model_a_id)")
cursor.execute("CREATE INDEX idx_pairwise_model_b ON pairwise_comparisons(model_b_id)")


now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
import hashlib

# Tính toán password_hash đúng cách
admin_password = "admin123"
admin_salt = "admin123"
admin_password_hash = hashlib.sha256((admin_password + admin_salt).encode()).hexdigest()

users_data = [
    ('admin', 'Admin System', admin_password_hash, admin_salt, 1, now, now)
]

cursor.executemany('INSERT INTO users (username, fullname, password_hash, salt, is_admin, last_login_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)', users_data)


# Lưu thay đổi vào database
conn.commit()

# Đóng kết nối
conn.close()