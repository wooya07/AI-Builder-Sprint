import sqlite3
from app.models import SavedTimetableRequest
from app import timetable_share


def test_saves_and_loads_timetable_with_share_code(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    def connection():
        result = sqlite3.connect(database_path)
        result.row_factory = sqlite3.Row
        result.execute("""
            CREATE TABLE IF NOT EXISTS saved_timetables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                share_code TEXT NOT NULL UNIQUE,
                timezone TEXT NOT NULL,
                classes_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        return result

    monkeypatch.setattr(timetable_share, "get_connection", connection)
    request = SavedTimetableRequest(
        classes=[{
            "courseId": "TEST101",
            "classGroupId": "TEST101-001",
            "courseName": "테스트 과목",
            "day": "MON",
            "startTime": "10:00",
            "endTime": "11:30",
        }]
    )
    saved = timetable_share.save_timetable(request)
    loaded = timetable_share.load_timetable(saved.code.lower())

    assert len(saved.code) == 8
    assert loaded is not None
    assert loaded.code == saved.code
    assert loaded.classes[0].class_group_id == "TEST101-001"
