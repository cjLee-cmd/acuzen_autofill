## Acuzen Autofill API (Backend)

이 레포는 GitHub Pages(프론트)에서 사용할 업로드/저장 API 백엔드입니다.

### 제공 API

- POST `/api/upload` — Base64로 전달된 CSV/XLSX를 파싱해 표준 레코드 목록을 반환
- POST `/api/cases` — 단일 케이스를 DB(SQLite)에 저장
- GET `/api/cases` — 저장된 케이스 전체 반환
- POST `/api/reset` — DB 초기화(테스트용)
- GET `/healthz` — 헬스체크

CORS/프리플라이트(OPTIONS)를 지원합니다.

### 빠른 시작 (로컬)

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py  # 기본 PORT=8000
```

### 환경변수

- `PORT`: 서비스 포트 (기본 8000)
- `DB_PATH`: SQLite 파일 경로 (기본 `./data/mock_cases.db`)
- `ALLOWED_ORIGINS`: 허용 오리진(콤마 구분). 미설정 시 `*`(데모용).

### Render 배포 예시

1) 새 GitHub 레포에 `backend/` 내용을 업로드 (예: `acuzen_autofill_api`)
2) Render 대시보드 → New Web Service → 해당 레포 선택
3) Build Command: `pip install -r requirements.txt`
4) Start Command: `python app.py`
5) 환경변수:
   - `ALLOWED_ORIGINS=https://cjlee-cmd.github.io`
   - (선택) `DB_PATH=/var/data/mock_cases.db`

배포 URL 예: `https://acuzen-autofill-api.onrender.com`

### 프론트와 연결(GitHub Pages)

프론트 URL에 백엔드 주소를 넘겨줍니다.

```
https://cjlee-cmd.github.io/acuzen_autofill/?api=https://acuzen-autofill-api.onrender.com
```

또는 프론트 `index.html`/`ui/mock_form.html`에 `window.API_BASE`를 하드코딩할 수 있습니다.

---

주의: 무료 호스팅의 디스크는 영속적이지 않을 수 있습니다. 장기 운영 시에는 Render Disk 또는 외부 DB(Postgres 등) 사용을 권장합니다.

