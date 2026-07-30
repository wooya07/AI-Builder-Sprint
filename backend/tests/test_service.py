from io import BytesIO
from openpyxl import Workbook
from app.catalog_import import read_catalog_excel


def test_reads_catalog_from_required_columns():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["\ud559\ub144", "\uad50\uacfc\ubaa9\uba85(\ubbf8\ud655\uc815\uad6c\ubd84)", "\uad50\uacfc\ubaa9\ubc88\ud638", "\ubd84\ubc18", "\ud559\uc810", "\uad50\uc218\uba85", "\uc2dc\uac04", "\uac1c\uc124\ud559\uacfc"])
    sheet.append(["2", "Data Structures", "CS201", "001", 3, "Kim", "\uc6d4 13:00-15:00", "Computer Science"])
    buffer = BytesIO()
    workbook.save(buffer)
    records, skipped_rows = read_catalog_excel(buffer.getvalue())
    assert records[0]["course_code"] == "CS201"
    assert records[0]["credits"] == 3
    assert skipped_rows == []
