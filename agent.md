# AI 자동화 에이전트 설계서 (agent.md)

## 1. 목적 및 범위

* **목적**: Excel의 행(레코드)을 **오라클(유사) DB에 데이터를 입력하는 웹/데스크톱 UI**에 자동 타이핑하여 등록한다.
* **기술 스택(실행 에이전트)**: Playwright, Selenium (둘 다 지원).
* **개발 보조**: Codex(코딩 에이전트)로 스캐폴딩 생성, 테스트/운영 자동화.
* **도메인**: 의학 약물감시(MedDRA 기반 AE/ADR 코딩 및 입력). *실제 MedDRA 코드는 라이선스가 필요하므로 PoC 단계에서는 **의사(MOCK) 코드**를 사용한다.*

> 참고: MedDRA는 5단계 위계(SOC→HLGT→HLT→PT→LLT) 구조이며, 실제 데이터 입력 시에는 보통 **LLT(또는 PT)**를 선택하고 버전 정보를 함께 보관한다. MedDRA 용어 선택은 최신 *Term Selection: Points to Consider* 원칙을 따른다.

---

## 2. 상위 아키텍처

1. Excel 업로드 → 2) **검증/정규화(스키마·룰 엔진)** → 3) **작업큐(Job)** → 4) **UI 에이전트(Playwright/Selenium)** → 5) 결과 수집(성공/실패·스크린샷) → 6) **로그/대시보드** → 7) 재시도/보류 처리

**컴포넌트**

* Ingestion: 업로드 API/포털(파일 해시·버전 관리)
* Validation: 스키마 검증, 도메인 룰(필수값·형식·범위)
* Mapping: Excel→UI 필드 매핑 카탈로그(셀렉터/라벨)
* Orchestration: 작업큐, 재시도 정책, 동시성 제어
* Execution: Playwright/Selenium 워커(헤드리스 포함)
* Observability: 구조화 로그, 메트릭, 스냅샷 저장(마스킹)
* Security: 자격증명 분리, 비밀관리, 감사추적

---

## 3. 데이터 스키마(입력 대상)

MedDRA 및 ICH E2B(R3) ICSR 필드 중 **UI 입력에 직접 필요한 최소 집합**을 채택(확장 가능). PoC에는 아래 **핵심 필드**를 사용한다.

### 3.1 핵심 필드 (PoC)

* `case_id` (문자열): 케이스 식별자
* `reporter_type` (코드): HCP/소비자/문헌 등
* `onset_date` (YYYY-MM-DD)
* `reaction_reported_term` (자연어): 보고된 증상 원문
* `meddra_level` (열거): LLT|PT (PoC에선 주로 LLT 목표)
* `meddra_term_text` (문자열): 선택된 MedDRA 텍스트(모의)
* `meddra_code` (문자열): 선택된 MedDRA 코드(모의)
* `meddra_version` (문자열): 예) v27.1 등(모의)
* `seriousness` (부울/코드): 중대성 여부(사망/입원 등 세부 값은 확장)
* `suspect_drug` (문자열)
* `dose_text` (문자열)
* `outcome` (코드): 회복/미회복/사망 등
* `narrative` (텍스트): 내러티브 요약

### 3.2 검증 룰(예)

* 필수: `case_id`, `reaction_reported_term`, `meddra_level`, `onset_date`
* 날짜: `onset_date`는 1970-01-01~오늘 사이
* MedDRA: `meddra_level`은 LLT|PT 중 하나, `meddra_code`와 `meddra_term_text`는 짝지어 존재
* 길이: `narrative` ≤ 4000자

---

## 4. Excel → UI 매핑 카탈로그(샘플)

* `case_id` → `#caseId`
* `reaction_reported_term` → `input[name="reportedTerm"]`
* `meddra_level` → `select#meddraLevel`
* `meddra_term_text` → `input[name="meddraText"]`
* `meddra_code` → `input[name="meddraCode"]`
* `meddra_version` → `input[name="meddraVersion"]`
* `onset_date` → `input[name="onsetDate"]`
* `seriousness` → `input[name="serious"]` (체크박스)
* `suspect_drug` → `input[name="suspectDrug"]`
* `dose_text` → `input[name="dose"]`
* `outcome` → `select#outcome`
* `narrative` → `textarea#narrative`

셀렉터 우선순위: `data-testid` > 안정적 CSS > 텍스트 근접 앵커 > XPath.

---

## 5. Playwright/Selenium 실행 정책

* **대기 전략**: 네트워크 유휴 + 요소 상태(visible/enabled) 동시 만족.
* **안전화 입력**: 각 필드 입력 후 **유효성 토스트/서버 응답** 확인 → 다음 필드로 진행.
* **재시도**: 요소탐지/일시 오류는 지수백오프(3회), 데이터 오류는 보류큐 이동.
* **증빙**: 레코드별 전/후 스크린샷 및 DOM 스냅샷 저장(민감정보 마스킹 규칙 적용).
* **동시성**: 워커 N개, 서버 부하 기준 스로틀링.

---

## 6. 보안·거버넌스

* 자격증명: 자동화 전용 계정, 비밀관리(Vault) 주입, 최소권한.
* 감사: JobID/행번호/시각/에이전트ID/결과코드/메시지/스냅샷 경로.
* 변경내성: UI 릴리스 노트 모니터링, 셀렉터 헬스 체크 알림.

---

## 7. 테스트 자산(로컬 샌드박스)

* **DB**: 경량 RDB(예: SQLite/Oracle XE 호환 스키마)로 `cases`, `reactions` 테이블.
* **UI**: 로컬 샘플 폼(단일 페이지) – 위 매핑된 필드 제공, 제출 시 DB insert.
* **데이터**: 100건 샘플 Excel (모의 MedDRA 코드·텍스트, 한/영 증상 혼합).

---

## 8. Codex 협업 가이드(프롬프트 패턴)

* “다음 스키마 DDL과 UI 필드 매핑을 바탕으로 Playwright 워커 스캐폴딩을 생성해. 각 필드 입력 후 유효성 토스트를 기다리고, 실패 시 스크린샷을 저장해. 동시 워커 2개, 지수백오프 재시도 3회.”
* “Selenium 대체 구현을 생성해. 셀렉터는 data-testid 우선. 실행 로그는 JSONL로 남겨.”
* “Excel 파서: 날짜/코드/필수값 검증 후 보류큐 CSV 분리. 통과 레코드만 작업큐에 넣어.”

---

## 9. SpecKit 명령 템플릿(설계 지향)

> *Spec-driven development*를 위해 GitHub **Spec Kit**(Specify CLI)를 사용한 흐름 예시.

```bash
# 1) 프로젝트 초기화 (선호 AI 에이전트는 팀 표준으로 교체)
specify init ae-autofill --ai copilot

# 2) 스펙 작성(템플릿 생성)
specify spec new --name "ui-autofill" --template webform-autofill

# 3) 시스템 컨텍스트 추가(아키텍처/제약/품질속성)
specify context add --file docs/architecture.md

# 4) 데이터 스키마/검증 룰 등록
specify data add --schema schemas/ae_core.yaml --rules rules/validation.yaml

# 5) UI 매핑 카탈로그 등록
specify mapping add --file mappings/ui_selectors.yaml

# 6) 테스트 아티팩트 선언(샘플 Excel, DB seed)
specify tests add --file tests/fixtures/ae_100.xlsx --type data
specify tests add --file tests/db/seed.sql --type db

# 7) 에이전트 태스크(Playwright/Selenium) 선언
specify tasks add --file tasks/autofill_playwright.yaml
specify tasks add --file tasks/autofill_selenium.yaml

# 8) 생성 미리보기 (코드 생성 전 차이 검토)
specify plan

# 9) 산출물 생성 (로컬 워크스페이스에 스캐폴딩)
specify generate --out ./build
```

**산출 파일(예)**

* `schemas/ae_core.yaml`: 필드/형식/필수값
* `rules/validation.yaml`: 도메인 룰(날짜/범위/상호의존)
* `mappings/ui_selectors.yaml`: CSS/XPath, 우선순위, 폴백 전략
* `tasks/autofill_playwright.yaml`: 흐름/대기/재시도/증빙 규칙
* `tasks/autofill_selenium.yaml`: 동등 작업 정의

---

## 10. 수용 기준(DoD)

* Excel 100건 배치 실행, **성공률 ≥ 99%**(데이터 오류 제외)
* 실패 건은 보류큐로 분리되고, 스크린샷·로그가 남는다
* UI 변경 시 셀렉터 폴백으로 자가 복구(최소 1회)
* 운영 리포트: 처리속도(X건/시간), 실패 사유 Top5, MedDRA(모의) 분포

---

## 11. 부록

* 라이선스 유의: 실제 MedDRA 코드는 MSSO 구독 필요. PoC는 모의 값 사용 → 운영 전 라이선스 확보 및 정식 용어 브라우저/API 연동 필요.
* 버전 관리: MedDRA는 연 2회(3/9월) 업데이트. 스키마/룰에 버전 필드 유지.
