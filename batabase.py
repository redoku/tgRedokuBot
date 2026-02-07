# database.py
import sqlite3

DB_NAME = "whitelist.db"

def init_db():
    """Создает таблицы requests и tickets"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица заявок (расширенная)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            nickname TEXT,
            age TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    
    conn.commit()
    conn.close()

def get_user(user_id):
    """Получает данные пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "user_id": row[0],
            "username": row[1],
            "nickname": row[2],
            "age": row[3],
            "status": row[4]
        }
    return None

def add_request(user_id, username, nickname, age):
    """Добавляет заявку"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO requests (user_id, username, nickname, age, status) VALUES (?, ?, ?, ?, 'pending')",
        (user_id, username, nickname, age)
    )
    conn.commit()
    conn.close()

def update_status(user_id, status):
    """Меняет статус заявки (approved/rejected)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE requests SET status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()

    conn.close()

