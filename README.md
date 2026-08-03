# 나만의 학기 시간표

수강편람을 기반으로 조건에 맞는 시간표를 추천하고, 수업 사이의 빈 시간에 개인 활동을 배치해 주는 웹 서비스입니다. 시간표 저장·불러오기, 회복 점수 분석, 수강편람 업로드를 지원합니다.

## 로컬 실행 가이드

### 1. 사전 요구 사항

- Git
- Node.js 20 이상 (LTS 권장)
- Python 3.12 (64비트 권장)

> Windows PowerShell 기준으로 작성했습니다. macOS/Linux에서는 가상환경 실행 파일 경로만 `.venv/bin/python`으로 바꾸면 됩니다.

### 2. 저장소 내려받기

```powershell
git clone https://github.com/wooya07/AI-Builder-Sprint.git
cd AI-Builder-Sprint
```

### 3. 백엔드 실행

새 PowerShell 창을 열고 아래 명령을 실행합니다.

```powershell
cd backend
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

정상 기동 확인:

- 상태 확인: [http://localhost:8000/health](http://localhost:8000/health)
- API 문서: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. 프런트엔드 실행

백엔드를 종료하지 않은 채, **별도의 PowerShell 창**에서 아래 명령을 실행합니다.

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

브라우저에서 [http://localhost:3000]에 접속합니다.

`http://localhost:3000`이 이미 사용 중이면 Next.js가 다른 포트를 제안할 수 있습니다. 이 경우 백엔드의 CORS 설정과 맞추기 위해 3000번 포트를 비운 뒤 다시 실행해 주세요.

## 환경 변수

`backend/.env`에 아래처럼 본인의 키를 설정합니다
```
UPSTAGE_API_KEY=up_your_key_here
```

## 빠른 기능 확인 순서

1. [http://localhost:3000]에서 **학기 시간표 추천** 교육과정 한글파일을 업로드한 후 수강할 과목을 선택, 탭의 조건을 선택한 뒤 `시간표 만들기`를 누릅니다.
  교육과정 한글파일 예제 다운로드 ->https://cse.pusan.ac.kr/cse/14274/subview.do
2. 추천 결과에서 `이 시간표 적용`을 눌러 주간 시간표에 반영합니다.
3. **빈 시간 채우기**에서 활동을 추가한 뒤 추천 기능과 회복 점수 계산을 확인합니다.
4. **전체 시간표 보기**에서 내보내기 코드를 발급하고, 같은 화면에서 코드를 입력해 불러오기를 확인합니다.

## 1. 사용한 AI 모델 및 서비스

| 구분 | 모델/서비스 | 사용 목적 | 실행 위치 | 장애 시 동작 |
|---|---|---|---|---|
| 운영 기능 | Upstage Solar Pro 3 (`solar-pro3`) | 수업 사이 빈 시간에 배치할 활동 추천 | 백엔드 서버 | 로컬 규칙 기반 추천으로 대체 |
| 운영 기능 | Upstage Document Parse (`document-parse`) | 교육과정표·수강 문서에서 표와 강의정보 추출 | 백엔드 서버 | 오류를 사용자용 HTTP 오류로 변환하며 자동 대체 모델은 없음 |
| 개발 보조 | OpenAI Codex | 코드 작성·수정 및 저장소 작업 보조 | 개발 환경 | 저장소의 `AGENTS.md` 지침에 따라 사람이 결과를 검토 |

### 모델 식별 정보에 대한 주의

- 운영 중 호출되는 모델명은 소스 코드에 각각 `solar-pro3`, `document-parse`로 명시되어 있다.
- 개발 보조 도구는 `AGENTS.md`에서 Codex 작업 지침을 확인할 수 있다.

## 2. AI API 사용 위치

### 2.1 활동 추천: Solar Pro 3

호출 흐름은 다음과 같다.

1. 브라우저가 `POST /api/v1/activities/recommend`를 호출한다.
2. FastAPI가 수업 일정에서 사용 가능한 시간대를 먼저 계산한다.
3. 백엔드가 Upstage Chat Completions API에 추천을 요청한다.
4. 모델 응답을 애플리케이션 스키마로 정규화하고 시간 범위·활동 길이를 검증한다.
5. API 키 누락, 외부 API 오류, JSON 파싱 실패 또는 유효 추천 부재 시 로컬 규칙 기반 알고리즘으로 대체한다.

| 항목 | 내용 | 코드 근거 |
|---|---|---|
| 프런트엔드 호출 | `POST /api/v1/activities/recommend` | [`frontend/app/page.tsx`](frontend/app/page.tsx#L236) |
| 백엔드 엔드포인트 | `recommend_activities()` | [`backend/app/main.py`](backend/app/main.py#L154) |
| 외부 API | `POST https://api.upstage.ai/v1/chat/completions` | [`backend/app/solar.py`](backend/app/solar.py#L20) |
| 모델 | `solar-pro3` | [`backend/app/solar.py`](backend/app/solar.py#L25) |
| 응답 형식 | JSON object 강제 | [`backend/app/solar.py`](backend/app/solar.py#L26) |
| 요청 제한시간 | 25초 | [`backend/app/solar.py`](backend/app/solar.py#L20) |
| 검증·정규화 | 활동 존재 여부, 시간 형식, 활동 길이, 빈 시간 포함 여부, 상태값 검사 | [`backend/app/solar.py`](backend/app/solar.py#L34) |
| 로컬 대체 | `make_local_recommendations()` | [`backend/app/main.py`](backend/app/main.py#L181) |

### 2.2 교육과정 문서 분석: Document Parse

호출 흐름은 다음과 같다.

1. 브라우저가 교육과정 문서를 `POST /api/v1/curriculum/parse`로 업로드한다.
2. 백엔드는 파일 확장자와 20MB 크기 제한을 확인한다.
3. 파일을 Upstage Document Digitization API로 전송한다.
4. 반환된 HTML/Markdown 표를 애플리케이션 소유 스키마로 변환한다.
5. 추출한 과목을 실제 강의 카탈로그와 매칭해 응답한다.

| 항목 | 내용 | 코드 근거 |
|---|---|---|
| 프런트엔드 호출 | `POST /api/v1/curriculum/parse` | [`frontend/app/page.tsx`](frontend/app/page.tsx#L441) |
| 백엔드 엔드포인트 | `parse_curriculum()` | [`backend/app/main.py`](backend/app/main.py#L94) |
| 외부 API | `POST https://api.upstage.ai/v1/document-digitization` | [`backend/app/document_parser.py`](backend/app/document_parser.py#L20) |
| 모델 | `document-parse` | [`backend/app/document_parser.py`](backend/app/document_parser.py#L167) |
| 파일 제한 | 최대 20MB | [`backend/app/document_parser.py`](backend/app/document_parser.py#L21) |
| 네트워크 제한시간 | 연결 10초, 응답 120초 | [`backend/app/document_parser.py`](backend/app/document_parser.py#L168) |
| 지원 확장자 | PDF, PNG, JPG/JPEG, TIFF, BMP, DOCX, PPTX, XLSX, HWP, HWPX | [`backend/app/main.py`](backend/app/main.py#L34) |

### 2.3 그 밖의 주요 내부 API

아래 API는 서비스 기능에 사용되지만 외부 AI 모델을 직접 호출하지 않는다.

| API | 역할 | 프런트엔드 코드 |
|---|---|---|
| `GET /api/v1/courses` | 강의 검색 | [`frontend/app/page.tsx`](frontend/app/page.tsx#L183) |
| `GET /api/v1/courses/credits` | 선택 강의 학점 조회 | [`frontend/app/page.tsx`](frontend/app/page.tsx#L166) |
| `POST /api/v1/timetables/generate` | 규칙 기반 학기 시간표 생성 | [`frontend/app/page.tsx`](frontend/app/page.tsx#L408) |
| `POST /api/v1/recovery/analyze` | 회복 점수 계산 | [`frontend/app/page.tsx`](frontend/app/page.tsx#L220) |
| `POST /api/v1/saved-timetables` | 시간표 저장 및 공유 코드 생성 | [`frontend/app/page.tsx`](frontend/app/page.tsx#L469) |
| `GET /api/v1/saved-timetables/{code}` | 공유 코드로 시간표 불러오기 | [`frontend/app/page.tsx`](frontend/app/page.tsx#L484) |
| `POST /api/v1/admin/course-catalog/import` | XLSX 강의 카탈로그 가져오기 | [`frontend/app/admin/page.tsx`](frontend/app/admin/page.tsx#L20) |
