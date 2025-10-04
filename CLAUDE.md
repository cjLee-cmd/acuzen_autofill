# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication Language

**IMPORTANT**: All conversations with the user must be conducted in Korean (한국어). Always respond in Korean regardless of the language used in code, documentation, or technical terms.

## Project Overview

**MedDRA Autofill Automation** - Excel-to-Web UI automation system for medical adverse event data entry using Playwright/Selenium. This PoC implements automated data entry into Oracle-like DB-backed web forms for MedDRA-based AE/ADR coding workflows.

**Domain**: Medical pharmacovigilance (MedDRA-based adverse event reporting)
**Tech Stack**: Python, Playwright (primary), Selenium (alternative), SQLite/Oracle-compatible DB
**Deployment**: Dual-mode (local scripts + deployable REST API via Render/Fly/Railway)

**Important**: Uses MOCK MedDRA codes for PoC (real MedDRA requires MSSO license). Production deployment requires licensing and official term browser integration.

## Architecture

7-stage pipeline:
1. **Ingestion** → 2. **Validation/Normalization** → 3. **Job Queue** → 4. **UI Worker (Playwright/Selenium)** → 5. **Result Collection** → 6. **Logging/Dashboard** → 7. **Retry/Dead Letter**

**Component Structure**:
```
src/meddra_autofill/
├── models.py              # CaseRecord, ValidationResult data models
├── ingestion/             # Excel/CSV parsing, normalization
├── validation/            # Schema + domain rule validation
├── mapping/               # Excel field → UI selector mapping catalog
├── queue/                 # Job queue with retry/dead-letter logic
├── execution/             # Playwright/Selenium workers
├── orchestration/         # Orchestrator coordinating pipeline stages
└── observability/         # Structured logging, reporting, metrics

backend/
└── app.py                 # Deployable REST API (upload, store, list cases)

ui/
└── mock_form.html         # Local test form for development

scripts/
├── run_batch.py           # CLI batch processor entry point
├── autofill_cases.py      # Single/multi-case automation runners
└── mock_server.py         # Local dev server for UI testing
```

## Core Data Schema

**MedDRA Fields** (ICH E2B subset for UI entry):
- `case_id`: Case identifier (required)
- `reaction_reported_term`: Symptom free-text (required)
- `meddra_level`: LLT|PT (required, default PT)
- `meddra_term_text`: Selected MedDRA term (mock)
- `meddra_code`: Corresponding code (mock)
- `meddra_version`: e.g., "MOCK-1.0" or "v27.1"
- `onset_date`: YYYY-MM-DD format (required)
- `seriousness`: Serious|Non-serious
- `suspect_drug`: Drug name
- `dose_text`: Dosage information
- `outcome`: Recovery status code
- `narrative`: Case narrative (≤4000 chars)

**Validation Rules**:
- Required: `case_id`, `reaction_reported_term`, `meddra_level`, `onset_date`
- Date range: 1970-01-01 to today
- MedDRA level: must be LLT or PT
- Narrative length: ≤4000 characters

## UI Field Mapping

**Selector Priority**: `data-testid` > stable CSS > text-based anchors > XPath

Example mappings (see [mapping/ui_mapping.py](src/meddra_autofill/mapping/ui_mapping.py)):
- `case_id` → `#caseId`
- `reaction_reported_term` → `input[name="reportedTerm"]`
- `meddra_level` → `select#meddraLevel`
- `onset_date` → `input[name="onsetDate"]`
- `seriousness` → `input[name="serious"]` (checkbox)
- `narrative` → `textarea#narrative`

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for real automation)
playwright install chromium
```

### Running Tests
```bash
# Run batch processing (dry-run mode, no real browser)
python scripts/run_batch.py data/sample_100.xlsx --dry-run

# Real automation against local test UI
python scripts/run_batch.py data/sample_100.xlsx \
  --target-url ui/mock_form.html \
  --report-json artifacts/report.json

# Single case automation
python scripts/autofill_one_case.py data/sample_100.xlsx --row 0

# Run E2E test suite
pytest tests/e2e/test_autofill_flow.py -v
```

### Local Development Server
```bash
# Start mock UI server
python scripts/mock_server.py
# Access at http://localhost:8001

# Start backend API server (for GitHub Pages integration)
python backend/app.py
# API available at http://localhost:8000
```

### Deployment (Backend API)
```bash
# Test API locally
curl -X POST http://localhost:8000/api/upload \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.csv", "content": "base64-encoded-csv"}'

# Deploy to Render/Fly/Railway (see Dockerfile + render.yaml)
```

## Playwright Worker Execution Policy

**Wait Strategy**: Network idle + element state (visible/enabled) both satisfied before interaction

**Safety Protocol**:
1. Fill each field sequentially
2. Wait for validation toast/server response after each input
3. Move to next field only after confirmation
4. Capture screenshot + DOM snapshot per record
5. Apply sensitive data masking rules

**Retry Logic**:
- Element detection failures: exponential backoff, 3 attempts
- Data validation errors: move to dead-letter queue (no retry)
- Network transients: retry with backoff

**Concurrency**: N workers with server load-based throttling

## Security & Governance

- **Credentials**: Automation-specific accounts, secrets via vault injection, least privilege
- **Audit Trail**: JobID, row number, timestamp, agent ID, result code, message, screenshot path
- **Change Resilience**: UI release note monitoring, selector health check alerts
- **Data Privacy**: Sensitive field masking in logs and screenshots

## Key Implementation Notes

1. **MedDRA Licensing**: Real MedDRA codes require MSSO subscription. Use mock data for PoC/testing.
2. **Selector Robustness**: Prefer `data-testid` attributes; implement fallback chains for UI changes.
3. **Date Parsing**: Support multiple formats (`%Y-%m-%d`, `%Y/%m/%d`, `%d-%m-%Y`, `%m/%d/%Y`).
4. **Dry-Run Mode**: Default worker behavior when Playwright not installed or `--dry-run` flag used.
5. **Dual Deployment**: Local CLI scripts + deployable REST API for GitHub Pages integration.

## Testing Assets

**Local Sandbox**:
- DB: SQLite (`artifacts/mock_cases.db`) with `cases` table
- UI: [ui/mock_form.html](ui/mock_form.html) - single-page form matching field mappings
- Data: 100-record sample Excel with mock MedDRA codes, mixed Korean/English terms

**Acceptance Criteria (DoD)**:
- 100-record batch execution: ≥99% success rate (excluding data errors)
- Failed records → dead-letter queue with screenshots + structured logs
- UI change resilience: automatic selector fallback (≥1 level)
- Operational reports: throughput (records/hour), top 5 failure reasons, MedDRA distribution

## AI Agent Collaboration Patterns

When working with this codebase:

1. **Scaffold Generation**: "Generate Playwright worker for [schema] with field-by-field validation waits, exponential backoff retry (3x), screenshot capture on failure."

2. **Selenium Alternative**: "Create Selenium equivalent using data-testid selectors, JSONL logging format."

3. **Validation Enhancement**: "Add validation rule: onset_date must be ≤report_date, narrative required when seriousness='Serious'."

4. **Mapping Extension**: "Update UI mapping catalog for new fields: reporter_country, age_group with fallback selectors."

5. **Monitoring**: "Add metrics: average fill time per field, validation error breakdown, worker utilization."

## Recent Work Context (from agent.md)

The project follows a **spec-driven development** approach with:
- Schema definitions in YAML for validation rules
- UI mapping catalogs with selector priorities and fallbacks
- Task definitions for Playwright/Selenium automation workflows
- Comprehensive observability with structured logging and evidence collection

**Architecture principles** from design doc:
- Defense in depth: validation → queue → execution → verification
- Fail-safe defaults: dry-run mode, graceful degradation when Playwright unavailable
- Evidence-based: screenshot + logs for every record processed
- Change resilience: selector health checks, fallback strategies
