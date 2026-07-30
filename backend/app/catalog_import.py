from io import BytesIO
import re
from openpyxl import load_workbook
from .repository import replace_courses

REQUIRED_FIELDS = {
    "\ud559\ub144": "grade",
    "\uad50\uacfc\ubaa9\uba85(\ubbf8\ud655\uc815\uad6c\ubd84)": "subject_name",
    "\uad50\uacfc\ubaa9\ubc88\ud638": "course_code",
    "\ubd84\ubc18": "section",
    "\ud559\uc810": "credits",
    "\uad50\uc218\uba85": "instructor",
    "\uc2dc\uac04": "schedule_text",
    "\uac1c\uc124\ud559\uacfc": "department",
}
OPTIONAL_FIELDS = {"\uc774\uc218\uad6c\ubd84": "subject_type", "\uad50\uacfc\uad6c\ubd84": "subject_type"}


def normalize_header(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def read_catalog_excel(content: bytes) -> tuple[list[dict[str, str | int]], list[int]]:
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    worksheet = workbook.active
    rows = worksheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration as error:
        raise ValueError("\uc5d1\uc140 \ud30c\uc77c\uc774 \ube44\uc5b4 \uc788\uc2b5\ub2c8\ub2e4.") from error
    indexed_headers = {normalize_header(value): index for index, value in enumerate(header_row)}
    missing = [header for header in REQUIRED_FIELDS if normalize_header(header) not in indexed_headers]
    if missing:
        raise ValueError("\ud544\uc218 \uc5f4\uc774 \uc5c6\uc2b5\ub2c8\ub2e4: " + ", ".join(missing))

    records: list[dict[str, str | int]] = []
    skipped_rows: list[int] = []
    for row_number, row in enumerate(rows, start=2):
        def cell(header: str) -> str:
            return str(row[indexed_headers[normalize_header(header)]] or "").strip()
        try:
            credits = int(float(cell("\ud559\uc810")))
            record: dict[str, str | int] = {
                "grade": cell("\ud559\ub144"), "subject_name": cell("\uad50\uacfc\ubaa9\uba85(\ubbf8\ud655\uc815\uad6c\ubd84)"),
                "course_code": cell("\uad50\uacfc\ubaa9\ubc88\ud638"), "section": cell("\ubd84\ubc18"), "credits": credits,
                "instructor": cell("\uad50\uc218\uba85"), "schedule_text": cell("\uc2dc\uac04"), "department": cell("\uac1c\uc124\ud559\uacfc"), "subject_type": "",
            }
            for header, target in OPTIONAL_FIELDS.items():
                if normalize_header(header) in indexed_headers:
                    record[target] = cell(header)
                    break
            if not all(str(record[key]).strip() for key in REQUIRED_FIELDS.values() if key != "credits") or credits < 1:
                raise ValueError
            records.append(record)
        except (ValueError, TypeError, IndexError):
            skipped_rows.append(row_number)
    if not records:
        raise ValueError("\uc800\uc7a5\ud560 \uc218 \uc788\ub294 \uac15\uc758\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.")
    return records, skipped_rows


def import_catalog(content: bytes) -> tuple[int, list[int]]:
    records, skipped_rows = read_catalog_excel(content)
    replace_courses(records)
    return len(records), skipped_rows
