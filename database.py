import os
import sqlite3
from pathlib import Path


DB_NAME = os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "mj_ai.db"))


def get_connection():
    """Open the configured SQLite database and create its parent directory."""
    db_path = Path(DB_NAME)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT NOT NULL,
            bot_message TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("PRAGMA table_info(messages)")
    columns = [row[1] for row in cursor.fetchall()]
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE messages ADD COLUMN user_id INTEGER")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            analysis_type TEXT NOT NULL,
            input_summary TEXT,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_message(user_message, bot_message, user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO messages (user_message, bot_message, user_id) VALUES (?, ?, ?)",
        (user_message, bot_message, user_id)
    )

    conn.commit()
    conn.close()


def clear_messages(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_messages(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_message, bot_message
        FROM messages
        WHERE user_id = ?
        ORDER BY id ASC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    chat_history = []

    for row in rows:
        chat_history.append({
            "user": row[0],
            "bot": row[1]
        })

    return chat_history


def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return None if row is None else {"id": row[0], "username": row[1], "password": row[2]}


def create_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)",
        (username, password)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def save_history(user_id, analysis_type, input_summary, result):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO analysis_history (user_id, analysis_type, input_summary, result) VALUES (?, ?, ?, ?)",
        (user_id, analysis_type, input_summary, result)
    )
    conn.commit()
    conn.close()


def get_history(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, analysis_type, input_summary, result, created_at FROM analysis_history WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "analysis_type": row[1],
            "input_summary": row[2],
            "result": row[3],
            "created_at": row[4]
        }
        for row in rows
    ]


def delete_history_record(history_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM analysis_history WHERE id = ? AND user_id = ?",
        (history_id, user_id)
    )
    conn.commit()
    conn.close()
