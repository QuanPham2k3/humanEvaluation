import os
import csv
import sqlite3
import argparse
from pathlib import Path
import datetime

def get_connection(db_path):
    """Tạo kết nối đến database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def import_data(db_path, audio_dir, csv_file=None, default_speaker_id=1, default_language='vi'):
    """
    Import audio files và metadata vào database từ:
    - Thư mục audio: static/audio/model_name/file.wav
    - File CSV (tùy chọn): chứa text scripts và thông tin model
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Đọc CSV nếu có
    csv_data = {}
    if csv_file and os.path.exists(csv_file):
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Giả sử định dạng CSV có cột filename, text, model_name
                filename = row.get('filename', '').strip()
                if filename:
                    csv_data[filename] = {
                        'text': row.get('text', ''),
                        'model_name': row.get('model_name', ''),
                        'speaker_name': row.get('speaker_name', ''),
                        'language': row.get('language', default_language)
                    }
    
    # Lấy danh sách models từ database
    existing_models = {}
    for row in cursor.execute("SELECT model_id, model_name FROM models"):
        existing_models[row['model_name']] = row['model_id']
    
    # Lấy danh sách speakers từ database
    existing_speakers = {}
    for row in cursor.execute("SELECT speaker_id, speaker_name FROM speakers"):
        existing_speakers[row['speaker_name']] = row['speaker_id']
    
    # Lấy danh sách samples hiện có trong DB
    existing_samples = set()
    for row in cursor.execute("SELECT audio_url FROM samples"):
        existing_samples.add(row['audio_url'])
    
    # Quét thư mục audio
    new_models = []
    new_samples = []
    
    for model_dir in os.listdir(audio_dir):
        model_path = os.path.join(audio_dir, model_dir)
        if not os.path.isdir(model_path):
            continue
        
        # Kiểm tra xem model có trong database chưa
        if model_dir not in existing_models:
            new_models.append((model_dir, f"Mô hình {model_dir}", now))
        
        # Quét các file trong thư mục model
        for file in os.listdir(model_path):
            if not file.lower().endswith(('.wav', '.mp3', '.ogg')):
                continue
            
            audio_url = f"audio/{model_dir}/{file}"
            
            # Bỏ qua nếu file đã có trong database
            if audio_url in existing_samples:
                continue
            
            # Lấy thông tin từ CSV nếu có, hoặc tạo mặc định
            filename = os.path.splitext(file)[0]
            if filename in csv_data:
                data = csv_data[filename]
                text = data['text']
                model_name = data['model_name'] or model_dir
                speaker_name = data['speaker_name']
                language = data['language']
            else:
                # Trích xuất text từ tên file nếu không có trong CSV
                text = filename.replace('_', ' ')
                model_name = model_dir
                speaker_name = None
                language = default_language
            
            # Lấy model_id
            if model_name in existing_models:
                model_id = existing_models[model_name]
            else:
                # Thêm model mới nếu chưa có
                if (model_name, f"Mô hình {model_name}", now) not in new_models:
                    new_models.append((model_name, f"Mô hình {model_name}", now))
                # Sẽ lấy model_id sau khi thêm vào database
                model_id = None
            
            # Lấy speaker_id
            speaker_id = default_speaker_id
            if speaker_name and speaker_name in existing_speakers:
                speaker_id = existing_speakers[speaker_name]
            
            # Xác định nếu là ground truth
            is_ground_truth = 1 if model_name.lower() in ['ground_truth', 'human', 'real'] else 0
            
            # Thêm vào danh sách samples mới
            new_samples.append((model_name, model_id, speaker_id, text, audio_url, language, is_ground_truth, 0, now))
    
    # Thêm models mới vào database
    if new_models:
        cursor.executemany(
            "INSERT INTO models (model_name, description, created_at) VALUES (?, ?, ?)",
            new_models
        )
        conn.commit()
        
        # Cập nhật model_id cho các samples mới
        for row in cursor.execute("SELECT model_id, model_name FROM models"):
            existing_models[row['model_name']] = row['model_id']
    
    # Cập nhật model_id cho các samples mới
    updated_samples = []
    for i, sample in enumerate(new_samples):
        model_name, _, speaker_id, text, audio_url, language, is_ground_truth, vote_count, created_at = sample
        if model_name in existing_models:
            model_id = existing_models[model_name]
            updated_samples.append((model_id, speaker_id, text, audio_url, language, is_ground_truth, vote_count, created_at))
    
    # Thêm samples mới vào database
    if updated_samples:
        cursor.executemany(
            """INSERT INTO samples 
               (model_id, speaker_id, text, audio_url, language, is_ground_truth, vote_count, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            updated_samples
        )
        conn.commit()
    
    # Kết quả
    results = {
        'new_models': len(new_models),
        'new_samples': len(updated_samples)
    }
    
    conn.close()
    return results

def main():
    parser = argparse.ArgumentParser(description='Import audio files và metadata vào database')
    parser.add_argument('--db', required=True, help='Đường dẫn đến database file')
    parser.add_argument('--audio', required=True, help='Đường dẫn đến thư mục audio')
    parser.add_argument('--csv', help='Đường dẫn đến file CSV chứa metadata')
    parser.add_argument('--speaker', type=int, default=1, help='Speaker ID mặc định (nếu không có trong CSV)')
    parser.add_argument('--language', default='vi', help='Ngôn ngữ mặc định (nếu không có trong CSV)')
    
    args = parser.parse_args()
    
    # Kiểm tra đường dẫn
    if not os.path.exists(args.db):
        print(f"Không tìm thấy database: {args.db}")
        return
    
    if not os.path.exists(args.audio):
        print(f"Không tìm thấy thư mục audio: {args.audio}")
        return
    
    # Import dữ liệu
    results = import_data(args.db, args.audio, args.csv, args.speaker, args.language)
    
    print(f"Đã thêm {results['new_models']} models mới")
    print(f"Đã thêm {results['new_samples']} samples mới")

if __name__ == "__main__":
    main()

#import_data.py --db data/tts_eval.db --audio static/audio