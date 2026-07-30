import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "course_catalog.db"


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grade TEXT NOT NULL,
                subject_name TEXT NOT NULL,
                subject_type TEXT NOT NULL,
                course_code TEXT NOT NULL,
                section TEXT NOT NULL,
                credits INTEGER NOT NULL,
                instructor TEXT NOT NULL,
                schedule_text TEXT NOT NULL,
                department TEXT NOT NULL,
                UNIQUE(course_code, section)
            )
        """)
