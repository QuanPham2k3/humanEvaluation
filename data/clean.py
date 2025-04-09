import sqlite3
import argparse

def connect_db(db_path):
    """Kết nối đến database"""
    conn = sqlite3.connect(db_path)
    return conn

def get_all_tables(conn):
    """Lấy danh sách tất cả các bảng trong database"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cursor.fetchall()]

def clear_table(conn, table_name):
    """Xóa tất cả dữ liệu từ một bảng cụ thể"""
    cursor = conn.cursor()
    try:
        cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        print(f"Lỗi khi xóa dữ liệu từ bảng {table_name}: {e}")
        return 0

def clear_all_tables(conn):
    """Xóa dữ liệu từ tất cả các bảng"""
    tables = get_all_tables(conn)
    results = {}
    
    # Tắt foreign key constraints tạm thời
    conn.execute("PRAGMA foreign_keys = OFF")
    
    for table in tables:
        if table != 'sqlite_sequence':  # Bỏ qua bảng hệ thống
            rows_deleted = clear_table(conn, table)
            results[table] = rows_deleted
    
    # Xóa các giá trị auto-increment counter
    conn.execute("DELETE FROM sqlite_sequence")
    
    # Bật lại foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    
    return results

def reset_database(db_path):
    """Xóa database hiện tại và tạo mới từ schema"""
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Đã xóa database: {db_path}")
    
    # Nếu có file schema.sql, có thể chạy lại nó để tạo database mới
    schema_path = os.path.join(os.path.dirname(db_path), "schema.sql")
    if os.path.exists(schema_path):
        conn = sqlite3.connect(db_path)
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
            conn.executescript(schema_sql)
        conn.close()
        print(f"Đã tạo lại database từ schema: {schema_path}")
    else:
        print("Không tìm thấy file schema.sql để tạo lại database.")

def main():
    parser = argparse.ArgumentParser(description='Clean database tables')
    parser.add_argument('--db', required=True, help='Đường dẫn đến database file')
    parser.add_argument('--table', help='Tên bảng cụ thể để xóa dữ liệu (để trống để xóa tất cả)')
    parser.add_argument('--reset', action='store_true', help='Xóa database và tạo lại từ schema.sql')
    
    args = parser.parse_args()
    
    if args.reset:
        reset_database(args.db)
        return
    
    conn = connect_db(args.db)
    
    if args.table:
        rows_deleted = clear_table(conn, args.table)
        print(f"Đã xóa {rows_deleted} dòng từ bảng {args.table}")
    else:
        results = clear_all_tables(conn)
        print("Kết quả xóa dữ liệu:")
        for table, rows in results.items():
            print(f"  - {table}: {rows} dòng")
    
    conn.close()

if __name__ == "__main__":
    main()

# clean all python clean_database.py --db data/tts_eval.db
# clean table python clean_database.py --db data/tts_eval.db --table table_name