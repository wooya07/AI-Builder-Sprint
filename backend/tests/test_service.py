from io import BytesIO
import json
from openpyxl import Workbook
from app import catalog_import
from app.catalog_import import read_catalog_excel


def test_reads_catalog_from_required_columns():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["\ud559\ub144", "\uad50\uacfc\ubaa9\uba85(\ubbf8\ud655\uc815\uad6c\ubd84)", "\uad50\uacfc\ubaa9\ubc88\ud638", "\ubd84\ubc18", "\ud559\uc810", "\uad50\uc218\uba85", "\uc2dc\uac04", "\uac1c\uc124\ud559\uacfc"])
    sheet.append(["2", "테스트 과목", "TEST101", "001", 3, "테스트 강사", "\uc6d4 13:00-15:00", "테스트 학과"])
    buffer = BytesIO()
    workbook.save(buffer)
    records, skipped_rows = read_catalog_excel(buffer.getvalue())
    assert records[0]["course_code"] == "TEST101"
    assert records[0]["credits"] == 3
    assert skipped_rows == []


def test_catalog_import_appends_only_new_class_groups(monkeypatch, tmp_path):
    catalog_path = tmp_path / "course_catalog.json"
    catalog_path.write_text(json.dumps({
        "timezone": "Asia/Seoul",
        "classes": [{"classGroupId": "OLD101-001", "courseId": "OLD101"}],
    }), encoding="utf-8")
    monkeypatch.setattr(catalog_import, "CATALOG_JSON_PATH", catalog_path)

    def record(code: str, section: str) -> dict[str, object]:
        return {
            "grade": "1", "subject_name": f"{code} course", "course_code": code,
            "section": section, "credits": 3, "instructor": "Teacher",
            "department": "Computer Science", "subject_type": "Major",
            "meetings": [{"day": "월", "start_minutes": 540, "duration_minutes": 75, "building": "101", "room": "201"}],
        }

    imported_count, duplicate_count = catalog_import.save_catalog_json([
        record("OLD101", "001"), record("NEW101", "001"),
    ])

    assert (imported_count, duplicate_count) == (1, 1)
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert [item["classGroupId"] for item in payload["classes"]] == ["OLD101-001", "NEW101-001"]

    unchanged_content = catalog_path.read_text(encoding="utf-8")
    imported_count, duplicate_count = catalog_import.save_catalog_json([record("NEW101", "001")])

    assert (imported_count, duplicate_count) == (0, 1)
    assert catalog_path.read_text(encoding="utf-8") == unchanged_content
