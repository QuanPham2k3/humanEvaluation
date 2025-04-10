import psycopg2
import os
import datetime
from config import DB_URL
import hashlib

def create_database():
    # Connect to PostgreSQL
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Drop tables if they exist
    cursor.execute("DROP TABLE IF EXISTS mos_ratings CASCADE")
    cursor.execute("DROP TABLE IF EXISTS ab_tests CASCADE")
    cursor.execute("DROP TABLE IF EXISTS visualization_dashboard CASCADE")
    cursor.execute("DROP TABLE IF EXISTS pairwise_comparisons CASCADE")  # Phải xóa trước models
    cursor.execute("DROP TABLE IF EXISTS users CASCADE")
    cursor.execute("DROP TABLE IF EXISTS samples CASCADE")
    cursor.execute("DROP TABLE IF EXISTS speakers CASCADE")
    cursor.execute("DROP TABLE IF EXISTS models CASCADE")
    
    # Create table models
    cursor.execute('''
    CREATE TABLE models (
        model_id SERIAL PRIMARY KEY,
        model_name TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create table speakers
    cursor.execute('''
    CREATE TABLE speakers (
        speaker_id SERIAL PRIMARY KEY,
        speaker_name TEXT NOT NULL,
        gender TEXT,
        age INTEGER,
        accent TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create table samples
    cursor.execute('''
    CREATE TABLE samples (
        sample_id SERIAL PRIMARY KEY,
        model_id INTEGER REFERENCES models(model_id) ON DELETE CASCADE,
        speaker_id INTEGER REFERENCES speakers(speaker_id) ON DELETE SET NULL,
        text TEXT NOT NULL,
        audio_url TEXT NOT NULL,
        language TEXT,
        is_ground_truth BOOLEAN DEFAULT FALSE,
        vote_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create table users
    cursor.execute('''
    CREATE TABLE users (
        user_id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,     
        fullname TEXT,     
        password_hash TEXT NOT NULL,
        salt TEXT,
        is_admin BOOLEAN DEFAULT FALSE,
        last_login_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create table mos_ratings
    cursor.execute('''
    CREATE TABLE mos_ratings (
        rating_id SERIAL PRIMARY KEY,
        sample_id INTEGER REFERENCES samples(sample_id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
        naturalness REAL CHECK (naturalness >= 1 AND naturalness <= 5),  
        intelligibility REAL CHECK (intelligibility >= 1 AND intelligibility <= 5),  
        pronunciation REAL CHECK (pronunciation >= 1 AND pronunciation <= 5),  
        prosody REAL CHECK (prosody >= 1 AND prosody <= 5),  
        speaker_similarity REAL CHECK (speaker_similarity >= 1 AND speaker_similarity <= 5 OR speaker_similarity IS NULL),  
        overall_rating REAL CHECK (overall_rating >= 1 AND overall_rating <= 5),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create table ab_tests
    cursor.execute('''
    CREATE TABLE ab_tests (
        test_id SERIAL PRIMARY KEY,
        sample_a_id INTEGER NOT NULL REFERENCES samples(sample_id) ON DELETE CASCADE,
        sample_b_id INTEGER NOT NULL REFERENCES samples(sample_id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
        selected_sample TEXT CHECK (selected_sample IN ('A', 'B', 'tie')),
        selection_reason TEXT,
        test_duration INTEGER,  -- Thời gian hoàn thành đánh giá (giây)
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create table visualization_dashboard
    cursor.execute('''
    CREATE TABLE visualization_dashboard (
        dashboard_id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        chart_type TEXT NOT NULL, -- 'bar', 'line', 'radar', 'heatmap', 'box_plot'
        data_source TEXT NOT NULL, -- SQL query hoặc reference tới view
        filter_criteria TEXT, -- JSON format của các bộ lọc
        axis_x TEXT, -- Trường dữ liệu cho trục X
        axis_y TEXT, -- Trường dữ liệu cho trục Y
        color_by TEXT, -- Trường dữ liệu phân nhóm màu
        created_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
        is_public BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Tạo bảng pairwise_comparisons
    cursor.execute('''
    CREATE TABLE pairwise_comparisons (
        comparison_id SERIAL PRIMARY KEY,
        test_name TEXT NOT NULL,
        test_description TEXT,
        model_a_id INTEGER NOT NULL REFERENCES models(model_id) ON DELETE CASCADE,
        model_b_id INTEGER NOT NULL REFERENCES models(model_id) ON DELETE CASCADE,
        total_votes INTEGER DEFAULT 0,
        model_a_wins INTEGER DEFAULT 0,
        model_b_wins INTEGER DEFAULT 0,
        tie_count INTEGER DEFAULT 0,
        preference_score REAL,
        p_value REAL,
        is_significant BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    #Create admin user
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admin_password = "admin123"
    admin_salt = "admin123"
    admin_password_hash = hashlib.sha256((admin_password + admin_salt).encode()).hexdigest()

    users_data = [
        ('admin', 'Admin System', admin_password_hash, admin_salt, True, now, now)
    ]
    cursor.executemany('INSERT INTO users (username, fullname, password_hash, salt, is_admin, last_login_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s)', users_data)

    # INDEX
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

    conn.commit()
    conn.close()
    
    print("Database schema created successfully!")

if __name__ == "__main__":
    create_database()