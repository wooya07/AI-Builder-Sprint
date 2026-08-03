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
키가 없어도 수강 조건 기반 시간표 추천, 시간표 편집·저장·불러오기, 회복 점수, 로컬 규칙 기반 활동 추천은 사용할 수 있습니다. 다만 **교육과정 파일 분석**은 Upstage API 키가 필요합니다.

## 빠른 기능 확인 순서

1. [http://localhost:3000]에서 **학기 시간표 추천** 교육과정 한글파일을 업로드한 후 수강할 과목을 선택, 탭의 조건을 선택한 뒤 `시간표 만들기`를 누릅니다.
  교육과정 한글파일 예제 다운로드 ->https://cse.pusan.ac.kr/cse/14274/subview.do
2. 추천 결과에서 `이 시간표 적용`을 눌러 주간 시간표에 반영합니다.
3. **빈 시간 채우기**에서 활동을 추가한 뒤 추천 기능과 회복 점수 계산을 확인합니다.
4. **전체 시간표 보기**에서 내보내기 코드를 발급하고, 같은 화면에서 코드를 입력해 불러오기를 확인합니다.