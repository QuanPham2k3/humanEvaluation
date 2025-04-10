import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import os
import datetime
from typing import List, Dict, Tuple, Optional, Any, Union

# ===== CONNECTION MANAGEMENT =====

def get_connection(db_url: str) -> psycopg2.extensions.connection:
    """Create a connection to PostgreSQL database"""
    return psycopg2.connect(db_url)

def execute_query(
    db_url: str, 
    query: str, 
    params: Optional[tuple] = None, 
    fetch_one: bool = False, 
    commit: bool = False
) -> Union[List[Dict], Dict, bool]:
    """Execute a query and return results"""
    conn = None
    try:
        conn = get_connection(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Ensure PostgreSQL parameter format
        query = query.replace('?', '%s')
        
        cursor.execute(query, params)
        
        if commit:
            conn.commit()
            if cursor.description:
                return cursor.fetchone() if fetch_one else cursor.fetchall()
            return True
        
        return cursor.fetchone() if fetch_one else cursor.fetchall()
    finally:
        if conn:
            conn.close()

# ===== USER MANAGEMENT =====

def get_user(db_url: str, username: str) -> Optional[Dict]:
    """Get user by username"""
    return execute_query(
        db_url, 
        "SELECT * FROM users WHERE username = %s", 
        (username,), 
        fetch_one=True
    )

def create_user(db_url: str, username: str, fullname: str, password: str, salt: str) -> Optional[Dict]:
    """Create a new user"""
    now = datetime.datetime.now()
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    
    return execute_query(
        db_url,
        """INSERT INTO users 
           (username, fullname, password_hash, salt, is_admin, last_login_at, updated_at) 
           VALUES (%s, %s, %s, %s, FALSE, %s, %s) RETURNING user_id""",
        (username, fullname, password_hash, salt, now, now),
        commit=True
    )

def update_login(db_url: str, user_id: int) -> bool:
    """Update user's last login timestamp"""
    now = datetime.datetime.now()
    return execute_query(
        db_url,
        "UPDATE users SET last_login_at = %s, updated_at = %s WHERE user_id = %s",
        (now, now, user_id),
        commit=True
    )

# ===== SAMPLE MANAGEMENT =====

def get_rated_samples(db_url: str, user_id: int) -> List[int]:
    """Get all sample IDs that have been rated by a user"""
    result = execute_query(
        db_url,
        "SELECT DISTINCT sample_id FROM mos_ratings WHERE user_id = %s",
        (user_id,)
    )
    return [row['sample_id'] for row in result] if result else []

def get_rated_ab_samples(db_url: str, user_id: int) -> List[Tuple[int, int]]:
    """Get sample pairs that have been rated by the user"""
    results = execute_query(
        db_url,
        "SELECT sample_a_id, sample_b_id FROM ab_tests WHERE user_id = %s",
        (user_id,)
    )
    return [(row['sample_a_id'], row['sample_b_id']) for row in results]

def get_ab_test_sample_pairs(
    db_url: str, 
    count: int = 5, 
    exclude_pairs: Optional[List[Tuple[int, int]]] = None, 
    model_a: Optional[str] = None
) -> List[Dict]:
    """Get multiple pairs of samples for batch A/B testing"""
    # Build query
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
    
    # Add model filter if specified
    if model_a:
        query += " AND m1.model_name = %s"
        params.append(model_a)
    
    query += " ORDER BY RANDOM() LIMIT %s"
    params.append(count * 2)  # Fetch extra pairs for filtering
    
    pairs = execute_query(db_url, query, params)
    
    # Filter excluded pairs
    if exclude_pairs:
        pairs = [
            pair for pair in pairs if not any(
                (pair['sample_a_id'], pair['sample_b_id']) == ex_pair or 
                (pair['sample_b_id'], pair['sample_a_id']) == ex_pair 
                for ex_pair in exclude_pairs
            )
        ]
    
    # Return only the requested number
    return pairs[:count]

def get_audio_path(url: str) -> str:
    """Get the full path for audio files"""
    import os
    return os.path.join("static", url)

def get_multiple_random_samples(
    db_url: str, 
    count: int = 10, 
    max_per_model: int = 5, 
    exclude_ids: Optional[List[int]] = None
) -> List[Dict]:
    """Get multiple random samples for MOS evaluation"""
    # Xây dựng câu truy vấn
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
    
    # Add exclusion filter if needed
    if exclude_ids and len(exclude_ids) > 0:
        placeholders = ','.join(['%s'] * len(exclude_ids))
        query += f" WHERE s.sample_id NOT IN ({placeholders})"
        params.extend(exclude_ids)
    
    # Complete query
    query += """
            GROUP BY s.sample_id, s.model_id, m.model_name
        )
        SELECT *
        FROM model_samples
        WHERE rn <= %s
        ORDER BY rating_count, RANDOM()
        LIMIT %s
    """
    
    params.extend([max_per_model, count])
    
    # Sử dụng execute_query cho nhất quán
    return execute_query(db_url, query, tuple(params))

def get_all_models(db_url: str) -> List[Dict]:
    """Get all model names from database"""
    
    return execute_query(db_url, "SELECT model_id, model_name FROM models")
# ===== RATING FUNCTIONS =====

def add_mos_rating(db_url: str, sample_id: int, user_id: int, ratings: Dict[str, float]) -> Optional[Dict]:
    """Save MOS rating"""
    now = datetime.datetime.now()
    sample_id = int(sample_id) if not isinstance(sample_id, int) else sample_id
    user_id = int(user_id) if not isinstance(user_id, int) else user_id
    
    return execute_query(
        db_url,
        """INSERT INTO mos_ratings 
           (sample_id, user_id, naturalness, intelligibility, pronunciation, 
            prosody, speaker_similarity, overall_rating, created_at) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING rating_id""",
        (
            sample_id, user_id, 
            ratings.get("naturalness"), 
            ratings.get("intelligibility"), 
            ratings.get("pronunciation"), 
            ratings.get("prosody"), 
            ratings.get("speaker_similarity"), 
            ratings.get("overall_rating"), 
            now
        ),
        commit=True
    )

def add_ab_rating(
    db_url: str, 
    sample_a_id: int, 
    sample_b_id: int, 
    user_id: int, 
    selected: str, 
    reason: str
) -> Optional[Dict]:
    """Save A/B test result"""
    now = datetime.datetime.now()
    return execute_query(
        db_url,
        """INSERT INTO ab_tests 
           (sample_a_id, sample_b_id, user_id, selected_sample, selection_reason, 
            test_duration, created_at) 
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING test_id""",
        (sample_a_id, sample_b_id, user_id, selected, reason, 0, now),
        commit=True
    )

# ===== ANALYTICS FUNCTIONS =====

def get_all_mos_data(db_url: str) -> List[Dict]:
    """Get all MOS ratings data with details for flexible analysis"""
    return execute_query(
        db_url,
        """SELECT r.rating_id, r.sample_id, r.user_id, 
                  r.naturalness, r.intelligibility, r.pronunciation, 
                  r.prosody, r.speaker_similarity, r.overall_rating,
                  r.created_at, m.model_name, u.username
           FROM mos_ratings r
           JOIN samples s ON r.sample_id = s.sample_id
           JOIN models m ON s.model_id = m.model_id
           JOIN users u ON r.user_id = u.user_id"""
    )

def get_ab_results(db_url: str) -> List[Dict]:
    """Get A/B test results summary"""
    return execute_query(
        db_url,
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
