# 백엔드

수강편람, 시간표 생성, 엑셀 수강편람 업로드 API를 제공하는 FastAPI 서버입니다.

## 사전 준비

- Python 3.12 (64비트 권장)
- PowerShell

Python 3.14 또는 불완전하게 생성된 가상환경에서는 `pydantic-core` 설치가 실패할 수 있습니다.

## 최초 설정

아래 명령어는 모두 `backend` 폴더에서 실행합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PowerShell의 가상환경 활성화 명령어는 필요하지 않습니다. `.venv\Scripts\python.exe`를 직접 호출하면 실행 정책 오류를 피할 수 있습니다.

## 개발 서버 실행

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

서버 실행 후 아래 주소에서 확인할 수 있습니다.

- 서버 상태 확인: http://localhost:8000/health
- API 문서(Swagger): http://localhost:8000/docs

서버는 `Ctrl+C`로 종료합니다.

## 가상환경 복구

패키지 설치가 실패하거나 `uvicorn` 명령을 찾지 못하면, 기존 가상환경을 삭제하고 다시 생성합니다.

```powershell
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## 수강편람 가져오기

서버를 실행한 뒤 API 문서에서 `POST /api/v1/admin/course-catalog/import`를 선택해 `.xlsx` 파일을 업로드합니다.

첫 번째 시트에 아래 열 이름이 있어야 합니다. 열의 순서는 상관없습니다.

| 필수 열 이름 | 저장 값 |
| --- | --- |
| 학년 | 학년 |
| 교과목명(미확정구분) | 교과목명 |
| 교과목번호 | 교과목번호 |
| 분반 | 분반 |
| 학점 | 학점 |
| 교수명 | 교수명 |
| 시간 | 시간 정보 |
| 개설학과 | 개설학과 |

가져오기는 10MB 이하의 `.xlsx` 파일만 지원합니다. 기존 수강편람 DB(`data/course_catalog.db`)는 업로드한 내용으로 교체되며, 필수 값이 없는 행은 제외됩니다.
