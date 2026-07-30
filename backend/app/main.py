from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from .catalog_import import import_catalog
from .database import initialize_database
from .models import CatalogImportResult, Course, TimetableRequest, TimetableResponse
from .repository import list_courses
from .service import generate_timetables

app = FastAPI(title="Personal Semester Planner API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/courses", response_model=list[Course])
def courses() -> list[Course]:
    return list_courses()


@app.post("/api/v1/admin/course-catalog/import", response_model=CatalogImportResult)
async def import_course_catalog(file: UploadFile = File(...)) -> CatalogImportResult:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported.")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size must not exceed 10MB.")
    try:
        imported_count, skipped_rows = import_catalog(content)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return CatalogImportResult(imported_count=imported_count, skipped_rows=skipped_rows, message="Course catalog saved.")


@app.post("/api/v1/timetables/generate", response_model=TimetableResponse)
def generate(request: TimetableRequest) -> TimetableResponse:
    return TimetableResponse(timetables=generate_timetables(request))
