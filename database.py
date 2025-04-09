import sqlite3
import hashlib
import os
import datetime
from contextlib import contextmanager

# Ensure data directory exists
if not os.path.exists('data'):
    os.makedirs('data')

@contextmanager
def get_connection(db_path):
    """Database connection context manager"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def execute_query(db_path, query, params=(), fetch_one=False, commit=False):
    """Execute query with optional commit"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        result = cursor.execute(query, params)
        if commit:
            conn.commit()
            return cursor.lastrowid
        if fetch_one:
            return result.fetchone()
        return result.fetchall()

# === User Authentication ===
def get_user(db_path, username):
    return execute_query(db_path, "SELECT * FROM users WHERE username = ?", (username,), fetch_one=True)

def create_user(db_path, username, fullname, password, salt):
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return execute_query(
        db_path,
        "INSERT INTO users (username, fullname, password_hash, salt, is_admin, last_login_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
        (username, fullname, password_hash, salt, now, now),
        commit=True
    )

def update_login(db_path, user_id):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute_query(
        db_path,
        "UPDATE users SET last_login_at = ?, updated_at = ? WHERE user_id = ?",
        (now, now, user_id),
        commit=True
    )

# === Sample Management ===
def get_rated_samples(db_path, user_id):
    """Get sample IDs that have been rated by the user"""
    return [row['sample_id'] for row in execute_query(
        db_path,
        "SELECT DISTINCT sample_id FROM mos_ratings WHERE user_id = ?",
        (user_id,)
    )]


def get_multiple_random_samples(db_path, count=10, max_per_model=5, exclude_ids=None):
    """
    Get multiple random samples for MOS evaluation, prioritizing samples with fewer ratings
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Xây dựng câu truy vấn trực tiếp
        query = """
            WITH model_samples AS (
                SELECT s.*, m.model_name,
                       COUNT(r.rating_id) as rating_count,
                       ROW_NUMBER() OVER(PARTITION BY s.model_id ORDER BY COUNT(r.rating_id), RANDOM()) as rn
                FROM samples s 
                JOIN models m ON s.model_id = m.model_id
                LEFT JOIN mos_ratings r ON s.sample_id = r.sample_id
        """
        
        params = []
        # Nếu có danh sách loại trừ (người dùng đã đánh giá)
        if exclude_ids and len(exclude_ids) > 0:
            placeholders = ','.join(['?'] * len(exclude_ids))
            query += f" WHERE s.sample_id NOT IN ({placeholders})"
            params.extend(exclude_ids)
        
        query += """
                GROUP BY s.sample_id, s.model_id, m.model_name
            )
            SELECT *
            FROM model_samples
            WHERE rn <= ?
            ORDER BY rating_count, RANDOM()
            LIMIT ?
        """
        
        params.extend([max_per_model, count])
        cursor.execute(query, params)
        
        # Chuyển kết quả về định dạng dict
        columns = [col[0] for col in cursor.description]
        result = []
        for row in cursor.fetchall():
            result.append(dict(zip(columns, row)))
        
        return result

def get_ab_test_samples(db_path):
    """Get random pair of samples for A/B testing"""
    return execute_query(
        db_path,
        """SELECT s1.sample_id as sample_a_id, s2.sample_id as sample_b_id,
                 s1.text, s1.audio_url as audio_a_url, s2.audio_url as audio_b_url,
                 m1.model_name as model_a_name, m2.model_name as model_b_name
          FROM samples s1, samples s2, models m1, models m2
          WHERE s1.text = s2.text AND s1.sample_id != s2.sample_id
                AND s1.model_id = m1.model_id AND s2.model_id = m2.model_id
                AND s1.model_id != s2.model_id
          ORDER BY RANDOM() LIMIT 1""",
        fetch_one=True
    )


# === Rating Functions ===
def add_mos_rating(db_path, sample_id, user_id, ratings):
    """Save MOS rating"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return execute_query(
        db_path,
        """INSERT INTO mos_ratings 
           (sample_id, user_id, naturalness, intelligibility, pronunciation, 
            prosody, speaker_similarity, overall_rating, created_at) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sample_id, user_id, ratings["naturalness"], ratings["intelligibility"], 
         ratings["pronunciation"], ratings["prosody"], ratings["speaker_similarity"], 
         ratings["overall_rating"], now),
        commit=True
    )

def add_ab_rating(db_path, sample_a_id, sample_b_id, user_id, selected, reason):
    """Save A/B test result"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return execute_query(
        db_path,
        """INSERT INTO ab_tests 
           (sample_a_id, sample_b_id, user_id, selected_sample, selection_reason, 
         test_duration, created_at) 
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (sample_a_id, sample_b_id, user_id, selected, reason, 0, now),
        commit=True
    )
def get_rated_ab_samples(db_path, user_id):
    """Get sample pairs that have been rated by the user"""
    results = execute_query(
        db_path,
        "SELECT sample_a_id, sample_b_id FROM ab_tests WHERE user_id = ?",
        (user_id,)
    )
    return [(row['sample_a_id'], row['sample_b_id']) for row in results]

def get_ab_test_sample_pairs(db_path, count=5, exclude_pairs=None, model_a=None):
    """Get multiple pairs of samples for batch A/B testing"""
    query = """
        SELECT s1.sample_id as sample_a_id, s2.sample_id as sample_b_id,
            s1.text, s1.audio_url as audio_a_url, s2.audio_url as audio_b_url,
            m1.model_name as model_a_name, m2.model_name as model_b_name
        FROM samples s1
        JOIN samples s2 ON s1.text = s2.text AND s1.sample_id != s2.sample_id
        JOIN models m1 ON s1.model_id = m1.model_id
        JOIN models m2 ON s2.model_id = m2.model_id
        WHERE s1.model_id != s2.model_id
    """
    
    params = []
    
    # Filter by model_a if provided
    if model_a:
        query += " AND m1.model_name = ?"
        params.append(model_a)
    
    # Exclude already rated pairs
    if exclude_pairs and len(exclude_pairs) > 0:
        # This is a bit complex for SQLite, so we'll keep it simple
        # We'll fetch more pairs than needed and filter in Python
        pass
    
    query += " ORDER BY RANDOM() LIMIT ?"
    params.append(count * 2)  # Fetch more than needed to account for filtering
    
    pairs = execute_query(db_path, query, params)
    
    # Filter out excluded pairs in Python
    if exclude_pairs and len(exclude_pairs) > 0:
        filtered_pairs = []
        for pair in pairs:
            if not any((pair['sample_a_id'], pair['sample_b_id']) == ex_pair or 
                    (pair['sample_b_id'], pair['sample_a_id']) == ex_pair 
                    for ex_pair in exclude_pairs):
                filtered_pairs.append(pair)
        pairs = filtered_pairs
    
    # Return only the requested number
    return pairs[:count]
# === Dashboard Data ===
def get_all_mos_data(db_path):
    """Get all MOS ratings data with details for flexible analysis"""
    return execute_query(
        db_path,
        """SELECT r.rating_id, r.sample_id, r.user_id, 
                  r.naturalness, r.intelligibility, r.pronunciation, 
                  r.prosody, r.speaker_similarity, r.overall_rating,
                  r.created_at, m.model_name, u.username
           FROM mos_ratings r
           JOIN samples s ON r.sample_id = s.sample_id
           JOIN models m ON s.model_id = m.model_id
           JOIN users u ON r.user_id = u.user_id"""
    )

def get_ab_results(db_path):
    """Get A/B test results summary"""
    rows = execute_query(
        db_path,
        """SELECT m1.model_name as model_a, m2.model_name as model_b,
                  COUNT(CASE WHEN a.selected_sample = 'A' THEN 1 END) as a_wins,
                  COUNT(CASE WHEN a.selected_sample = 'B' THEN 1 END) as b_wins,
                  COUNT(CASE WHEN a.selected_sample = 'tie' THEN 1 END) as ties,
                  COUNT(*) as total
           FROM ab_tests a
           JOIN samples s1 ON a.sample_a_id = s1.sample_id
           JOIN samples s2 ON a.sample_b_id = s2.sample_id
           JOIN models m1 ON s1.model_id = m1.model_id
           JOIN models m2 ON s2.model_id = m2.model_id
           GROUP BY m1.model_name, m2.model_name"""
    )
    # Chuyển đổi sqlite3.Row thành list of dicts
    return [dict(row) for row in rows]