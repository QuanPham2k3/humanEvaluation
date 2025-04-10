import os
import csv
import psycopg2
from psycopg2.extras import DictCursor
import argparse

import datetime
from typing import Dict, List, Set, Tuple, Optional
from config import get_db_url

# ===== DATABASE CONNECTION =====

def get_connection(db_url: str) -> psycopg2.extensions.connection:
    """Create a connection to PostgreSQL database"""
    try:
        conn = psycopg2.connect(db_url)
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        raise

# ===== DATABASE OPERATIONS =====

def get_existing_models(cursor) -> Dict[str, int]:
    """Get all existing models from database"""
    cursor.execute("SELECT model_id, model_name FROM models")
    return {row['model_name']: row['model_id'] for row in cursor}

def get_existing_speakers(cursor) -> Dict[str, int]:
    """Get all existing speakers from database"""
    cursor.execute("SELECT speaker_id, speaker_name FROM speakers")
    return {row['speaker_name']: row['speaker_id'] for row in cursor}

def get_existing_samples(cursor) -> Set[str]:
    """Get all existing audio URLs from database"""
    cursor.execute("SELECT audio_url FROM samples")
    return {row['audio_url'] for row in cursor}

def create_speaker(cursor, speaker_id: int, speaker_name: str, description: str, created_at: str) -> None:
    """Create a speaker in the database"""
    cursor.execute(
        "INSERT INTO speakers (speaker_id, speaker_name, description, created_at) VALUES (%s, %s, %s, %s)",
        (speaker_id, speaker_name, description, created_at)
    )

def insert_models(cursor, models: List[Tuple]) -> None:
    """Insert multiple models into database"""
    if not models:
        return
    
    cursor.executemany(
        "INSERT INTO models (model_name, description, created_at) VALUES (%s, %s, %s)",
        models
    )

def insert_samples(cursor, samples: List[Tuple]) -> None:
    """Insert multiple samples into database"""
    if not samples:
        return
    
    cursor.executemany(
        """INSERT INTO samples 
           (model_id, speaker_id, text, audio_url, language, is_ground_truth, vote_count, created_at) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        samples
    )

def insert_speakers(cursor, speakers: List[Tuple]) -> None:
    """Insert multiple speakers into database"""
    if not speakers:
        return
    
    cursor.executemany(
        "INSERT INTO speakers (speaker_name, description, created_at) VALUES (%s, %s, %s)",
        speakers
    )

def ensure_default_speaker_exists(db_url: str, speaker_id: int = 1, speaker_name: str = "Default") -> None:
    """Ensure a default speaker exists in the database"""
    conn = get_connection(db_url)
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Check if speaker exists
        cursor.execute("SELECT speaker_id FROM speakers WHERE speaker_id = %s", (speaker_id,))
        if cursor.fetchone() is None:
            create_speaker(cursor, speaker_id, speaker_name, "Default speaker", now)
            conn.commit()
            print(f"Created default speaker: {speaker_name}")
    finally:
        cursor.close()
        conn.close()

# ===== DATA PROCESSING =====

def read_csv_data(csv_file: str, default_language: str) -> Dict:
    """Read data from CSV file"""
    if not csv_file or not os.path.exists(csv_file):
        return {}
    
    csv_data = {}
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get('filename', '').strip()
            if filename:
                csv_data[filename] = {
                    'text': row.get('text', ''),
                    'model_name': row.get('model_name', ''),
                    'speaker_name': row.get('speaker_name', ''),
                    'language': row.get('language', default_language)
                }
    return csv_data

def extract_new_speakers_from_csv(csv_data: Dict, existing_speakers: Dict, created_at: str) -> List[Tuple]:
    """Extract new speakers from CSV data"""
    new_speakers = []
    for data in csv_data.values():
        speaker_name = data.get('speaker_name')
        if speaker_name and speaker_name not in existing_speakers:
            new_speakers.append((speaker_name, f"Speaker {speaker_name}", created_at))
    return new_speakers

def process_audio_files(audio_dir: str, csv_data: Dict, existing_models: Dict, 
                        existing_speakers: Dict, existing_samples: Set, 
                        default_speaker_id: int, default_language: str, 
                        created_at: str) -> Tuple[List, List]:
    """Process audio files from directory and prepare data for database insertion"""
    new_models = []
    new_samples = []
    
    for model_dir in os.listdir(audio_dir):
        model_path = os.path.join(audio_dir, model_dir)
        if not os.path.isdir(model_path):
            continue
        
        # Check if model exists in database
        if model_dir not in existing_models:
            new_models.append((model_dir, f"Model {model_dir}", created_at))
        
        # Scan files in model directory
        for file in os.listdir(model_path):
            if not file.lower().endswith(('.wav', '.mp3', '.ogg')):
                continue
            
            audio_url = f"audio/{model_dir}/{file}"
            
            # Skip if file already exists in database
            if audio_url in existing_samples:
                continue
            
            # Get information from CSV if available, or create default
            if file in csv_data:
                data = csv_data[file]
                text = data['text']
                model_name = data['model_name'] or model_dir
                speaker_name = data['speaker_name']
                language = data['language']
            else:
                # Extract text from filename if not in CSV
                text = file.replace('_', ' ').replace('.wav', '').replace('.mp3', '').replace('.ogg', '')
                model_name = model_dir
                speaker_name = None
                language = default_language
            
            # Get model_id
            if model_name in existing_models:
                model_id = existing_models[model_name]
            else:
                # Add new model if it doesn't exist
                if (model_name, f"Model {model_name}", created_at) not in new_models:
                    new_models.append((model_name, f"Model {model_name}", created_at))
                # Will get model_id after adding to database
                model_id = None
            
            # Get speaker_id
            speaker_id = default_speaker_id
            if speaker_name and speaker_name in existing_speakers:
                speaker_id = existing_speakers[speaker_name]
            
            # Determine if ground truth
            is_ground_truth = True if model_name.lower() in ['ground_truth', 'human', 'real'] else False
            
            # Add to new samples list
            new_samples.append((model_name, model_id, speaker_id, text, audio_url, language, is_ground_truth, 0, created_at))
    
    return new_models, new_samples

def prepare_samples_for_insertion(new_samples: List[Tuple], existing_models: Dict) -> List[Tuple]:
    """Prepare sample data for insertion with correct model_id"""
    updated_samples = []
    for sample in new_samples:
        model_name, _, speaker_id, text, audio_url, language, is_ground_truth, vote_count, created_at = sample
        if model_name in existing_models:
            model_id = existing_models[model_name]
            updated_samples.append((model_id, speaker_id, text, audio_url, language, is_ground_truth, vote_count, created_at))
    return updated_samples

# ===== MAIN IMPORT FUNCTION =====

def import_data(db_url: str, audio_dir: str, csv_file: Optional[str] = None, 
                default_speaker_id: int = 1, default_language: str = 'en') -> Dict:
    """
    Import audio files and metadata into database.
    
    Args:
        db_url: PostgreSQL connection URL
        audio_dir: Directory containing audio files organized by model folders
        csv_file: Optional CSV file with metadata
        default_speaker_id: Default speaker ID to use when not specified
        default_language: Default language code
        
    Returns:
        Dictionary with import statistics
    """
    conn = get_connection(db_url)
    cursor = conn.cursor(cursor_factory=DictCursor)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Read metadata from CSV if available
        csv_data = read_csv_data(csv_file, default_language)
        
        # Get existing database records
        existing_models = get_existing_models(cursor)
        existing_speakers = get_existing_speakers(cursor)
        existing_samples = get_existing_samples(cursor)
        
        # Process and add new speakers from CSV
        if csv_data:
            new_speakers = extract_new_speakers_from_csv(csv_data, existing_speakers, now)
            
            if new_speakers:
                insert_speakers(cursor, new_speakers)
                conn.commit()
                
                # Update speakers dictionary with new entries
                existing_speakers = get_existing_speakers(cursor)
                print(f"Added {len(new_speakers)} new speakers")
        
        # Make sure default speaker exists
        if str(default_speaker_id) not in [str(id) for id in existing_speakers.values()]:
            ensure_default_speaker_exists(db_url, default_speaker_id)
            existing_speakers = get_existing_speakers(cursor)
        
        # Process audio files and prepare data
        new_models, new_samples = process_audio_files(
            audio_dir, csv_data, existing_models, existing_speakers, 
            existing_samples, default_speaker_id, default_language, now
        )
        
        # Add new models to database
        if new_models:
            insert_models(cursor, new_models)
            conn.commit()
            
            # Update models dictionary with new entries
            existing_models = get_existing_models(cursor)
        
        # Prepare and add new samples
        updated_samples = prepare_samples_for_insertion(new_samples, existing_models)
        
        if updated_samples:
            insert_samples(cursor, updated_samples)
            conn.commit()
        
        # Return statistics
        return {
            'new_models': len(new_models),
            'new_samples': len(updated_samples)
        }
    
    finally:
        cursor.close()
        conn.close()

# ===== COMMAND LINE INTERFACE =====

def main():
    """Main entry point for command line usage"""
    parser = argparse.ArgumentParser(description='Import audio files and metadata into TTS evaluation database')
    parser.add_argument('--db', required=False, help='Database URL (not required if configured in config.py)')
    parser.add_argument('--audio', required=True, help='Path to audio directory')
    parser.add_argument('--csv', help='Path to CSV file containing metadata')
    parser.add_argument('--speaker', type=int, default=1, help='Default speaker ID')
    parser.add_argument('--language', default='en', help='Default language code')
    
    args = parser.parse_args()
    
    # Get database URL
    db_url = args.db if args.db else get_db_url()
    
    # Verify audio directory exists
    if not os.path.exists(args.audio):
        print(f"Error: Audio directory not found: {args.audio}")
        return 1
    
    # Import data
    try:
        results = import_data(db_url, args.audio, args.csv, args.speaker, args.language)
        print(f"Import successful:")
        print(f"- Added {results['new_models']} new models")
        print(f"- Added {results['new_samples']} new samples")
        return 0
    except Exception as e:
        print(f"Error during import: {e}")
        return 1

if __name__ == "__main__":
    main()

# Usage examples:
# Basic usage: python import_data.py --audio static/audio
# With metadata: python import_data.py --audio static/audio --csv static/tts_files.csv
# Custom language: python import_data.py --audio static/audio --language en