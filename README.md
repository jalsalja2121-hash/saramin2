# 채용 업무 Streamlit PoC

Python으로 작성한 세 가지 기능을 Streamlit에서 실행합니다.

| 기능 | 입력 | 결과 |
|---|---|---|
| 1. LLM 채용 공고 분석 | 공고 원문 | 회사·직무·경력·조건·전형·누락 정보, 원문 근거, JSON |
| 2. 문서 작성 도구 | 분석 결과 + 작성자 메모 | 직접 편집할 수 있는 분석 보고서, TXT/HTML 다운로드 |
| 3. 업무 자동화 도구 | 보고서 + 사이트 설정 | Selenium 입력, 저장 버튼 클릭, 화면 캡처, 로컬 SQLite 저장 검증 |

별도의 JavaScript/Node 서버 없이 Python만 실행합니다. 테스트 페이지와 다운로드용 HTML도 Python에서 생성합니다.
이 PoC는 버튼으로 각 단계를 실행하는 명시적 워크플로입니다. LLM이 도구를 자율 선택하는 에이전트는 아닙니다.

## 빠른 시작

Python 3.10 이상과 Chrome 또는 Edge가 필요합니다. 개발·검증 환경은 Python 3.12, Chrome입니다.

프로젝트 폴더의 PowerShell에서:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

이 프로젝트에는 `.venv`를 준비해 두었습니다. 현재 컴퓨터에서는 마지막 명령만 실행하면 됩니다.
브라우저에서 <http://127.0.0.1:8501>에 접속합니다. 종료는 실행 터미널에서 `Ctrl+C`입니다.
포트가 사용 중이면 `run.py --server.port 8502`로 실행합니다.

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

## 1. 채용 공고 분석

### 데모 모드

API 키 없이 기본 가상 공고로 전체 흐름을 확인합니다. **LLM이 아닌 규칙 기반 추출**입니다.
`회사:`, `직무:`, `근무지:`, `고용형태:`, `경력:`, `마감일:` 및
`[주요 업무]`, `[필수 조건]`, `[우대 사항]`, `[전형 절차]` 형식을 인식합니다.
임의 형식 공고의 의미 이해나 실제 LLM 정확도를 평가하는 용도가 아닙니다.

### 실제 LLM 모드

`.streamlit/secrets.toml`의 `GEMINI_API_KEY`에 Gemini 키를 한 번 저장하면 실제 LLM 모드로 자동 연결됩니다.
화면에 API 키 입력란은 없습니다. 키가 없으면 규칙 기반 데모로 실행됩니다.
설정 파일을 처음 생성한 경우 앱을 재시작한 뒤 브라우저를 새로고침하세요.
기본 모델명은 요청한 `gemini-3.8-flash`입니다. `GEMINI_MODEL` 환경변수 또는 설정 파일에서 변경할 수 있습니다.
공식 Google GenAI SDK의 `client.interactions.create`와 JSON Schema/Pydantic 구조화 출력을 사용합니다.
API 키는 백엔드에서만 읽으며 화면에 표시하지 않습니다. OpenAI API 키는 사용하지 않습니다.
`store=False`로 호출하며, 공고는 분석을 위해 Google Gemini로 전송됩니다.
실제 LLM 호출은 사용자의 API 키가 필요하며 API 요금이 발생할 수 있습니다.

`.streamlit/secrets.toml` 설정 예시 (`GEMINI_API_KEY`/`GOOGLE_API_KEY` 환경변수가 있으면 우선 적용):

```toml
GEMINI_API_KEY = "사용자의 Gemini API 키"
GEMINI_MODEL = "gemini-3.8-flash"
```

키 파일은 Git 제외 대상입니다. 분석 원문은 30~30,000자로 제한합니다.
누락 정보는 추정하지 않도록 지시하고, 목록의 원문 인용이 실제 입력에 포함되는지 검증합니다.
인용 일치가 분석 해석 전체의 정확성을 보장하지는 않으므로 실제 활용 전 원문을 확인하세요.

## 2. 문서 작성

분석 후 `문서 작성` 탭 → 메모 입력 → `보고서 생성`을 누릅니다.
문서 제목과 본문을 직접 수정하고 TXT 또는 HTML을 다운로드합니다.
HTML은 브라우저에서 인쇄하거나 PDF로 저장할 수 있습니다. DOCX/PDF 직접 생성은 포함하지 않습니다.
보고서는 추출 결과를 결정론적 템플릿으로 구성하며, 별도 LLM 비용 없이 생성합니다.
공고·모드·모델·메모를 변경하면 이전 문서를 다음 단계로 넘길 수 없으며 재생성이 필요합니다.

## 3. Selenium 입력 및 저장

### 로컬 데모

1. `업무 자동화` 탭 → `로컬 데모 사이트` 선택.
2. `입력만 확인`으로 실행하면 필드별 입력값과 캡처를 확인합니다.
3. `입력 후 저장`으로 실행하면 저장 버튼을 누르고 DB 값까지 대조합니다.
4. 결과 화면에서 저장 데이터와 JSON을 내려받을 수 있습니다.

실행할 때만 `127.0.0.1`의 임시 포트에서 데모 사이트를 열고, 완료 후 서버와 브라우저를 닫습니다.
데이터는 `outputs/submissions.sqlite3`에 저장합니다. 동일 세션·동일 내용은 실행 ID를 사용해 중복 저장을 방지합니다.
새 세션에서 같은 내용을 실행하면 새 기록입니다. 입력만 확인할 때는 DB 행을 추가하지 않습니다.
보고서와 분석은 Streamlit 세션에만 남아 새로고침/세션 종료 시 사라질 수 있습니다.

Selenium Manager가 드라이버를 준비하므로 최초 실행에 인터넷 접속이 필요할 수 있습니다.
자동 설치가 차단된 환경에서는 브라우저와 버전이 맞는 드라이버를 준비하고 경로를 설정합니다:

```powershell
$env:WEBDRIVER_PATH = 'C:\tools\chromedriver.exe'
# 브라우저 설치 위치가 표준 경로가 아닌 경우에만:
$env:BROWSER_BINARY = 'C:\tools\chrome.exe'
.\.venv\Scripts\python.exe run.py
```

Edge 선택 시에는 Edge 드라이버 경로를 사용해야 합니다. 브라우저는 앱 서버가 실행되는 컴퓨터에서 동작합니다.

### 사용자 지정 사이트

대상 사이트를 정하지 않은 상태에서도 확장할 수 있도록 설정 입력을 제공합니다.
실제 사이트에 맞는 URL과 CSS 선택자를 입력합니다:

```json
{
  "url": "https://example.com/form",
  "fields": {
    "company": "#company",
    "role": "#role",
    "title": "#title",
    "body": "#body"
  },
  "submit": "#submit",
  "success": "#success"
}
```

`example.com/form`은 설명용 자리표시자이며 동작하는 사이트가 아닙니다.
`fields`는 일반 텍스트 input/textarea, `submit`은 저장 버튼, `success`는 새 저장 완료 시에만 나타나는 요소를 가리켜야 합니다.
사용자 지정 사이트는 완료 요소 표시까지만 검증하며 해당 서비스의 DB 저장까지 검증하지 않습니다.
로그인/MFA/CAPTCHA, iframe, 드롭다운, 에디터, 파일 업로드는 사이트별 어댑터가 필요합니다.
현재는 새 브라우저 세션으로 실행하므로 기존 브라우저의 로그인 상태를 가져오지 않습니다.
외부 저장 요청은 자동 재시도하지 않습니다. 완료 확인 실패 시 저장됐을 수도 있으니 사이트에서 확인하세요.

로컬 개인용 PoC입니다. 다중 사용자 공개 서버용 인증·권한·감사·사이트 허용목록은 구현하지 않았습니다.

## 코드 구조

```text
streamlit_app.py          # 3개 탭, 상태 연결, 다운로드
run.py                   # 앱 실행
hiring_poc/
  analysis.py            # 데모 추출 + 실제 Gemini 구조화 분석
  settings.py            # 백엔드 키/모델 설정
  documents.py           # 보고서 + HTML 생성
  automation.py          # Selenium 입력/저장/확인
  demo_site.py           # Python HTTP 서버 + SQLite
tests/test_workflow.py    # 기능/화면/실제 브라우저 테스트
```

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q -m 'not browser'
$env:RUN_BROWSER_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q -m browser
```

확인 항목: 조건 분리, 누락 정보, HTML 이스케이프, API 호출 계약과 잘못된 인용 거부,
화면 생성·편집·이전 결과 무효화, HTTP 저장 중복 방지, 실제 Chrome 입력만 확인/저장/DB 일치.
실제 LLM 유료 호출 및 특정 외부 채용 사이트 연동은 검증하지 않았습니다.

## 구현 참고

- [Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)
- [Selenium 명시적 대기](https://www.selenium.dev/documentation/webdriver/waits/)
- [Selenium Manager](https://www.selenium.dev/documentation/selenium_manager/)
- Streamlit 1.64.0 설치 패키지의 개발 가이드와 AppTest를 사용했습니다.
