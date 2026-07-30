import json
import secrets
import sqlite3
import string
from .database import get_connection
from .models import SavedTimetableRequest, SavedTimetableResponse, ScheduledClass

ALPHABET = string.ascii_uppercase + string.digits


def _new_code(length: int = 8) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def save_timetable(timetable: SavedTimetableRequest) -> SavedTimetableResponse:
    classes_json = json.dumps(
        [item.model_dump() for item in timetable.classes],
        ensure_ascii=False,
    )
    with get_connection() as connection:
        for _ in range(10):
            code = _new_code()
            try:
                connection.execute(
                    "INSERT INTO saved_timetables (share_code, timezone, classes_json) VALUES (?, ?, ?)",
                    (code, timetable.timezone, classes_json),
                )
                return SavedTimetableResponse(
                    code=code, timezone=timetable.timezone, classes=timetable.classes
                )
            except sqlite3.IntegrityError:
                continue
    raise RuntimeError("시간표 코드를 생성하지 못했습니다.")


def load_timetable(code: str) -> SavedTimetableResponse | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT share_code, timezone, classes_json FROM saved_timetables WHERE share_code = ?",
            (code.strip().upper(),),
        ).fetchone()
    if not row:
        return None
    return SavedTimetableResponse(
        code=row["share_code"],
        timezone=row["timezone"],
        classes=[ScheduledClass.model_validate(item) for item in json.loads(row["classes_json"])],
    )
