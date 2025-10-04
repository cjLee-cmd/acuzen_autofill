"""Simple HTTP server that stores submitted cases into SQLite."""
from __future__ import annotations

import base64
import binascii
import json
import sqlite3
import sys
import tempfile
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from meddra_autofill.ingestion.excel_ingestion import ExcelIngestor
from meddra_autofill.ingestion.normalizer import RecordNormalizer
from meddra_autofill.models import CaseRecord, records_from_iterable

ARTIFACT_DIR = ROOT_DIR / "artifacts"
DB_PATH = ARTIFACT_DIR / "mock_cases.db"


def init_db() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                reaction_reported_term TEXT,
                meddra_level TEXT,
                meddra_term_text TEXT,
                meddra_code TEXT,
                meddra_version TEXT,
                onset_date TEXT,
                seriousness TEXT,
                suspect_drug TEXT,
                dose_text TEXT,
                outcome TEXT,
                narrative TEXT,
                raw_payload TEXT
            )
            """
        )
        conn.commit()


class CaseRequestHandler(SimpleHTTPRequestHandler):
    """Serve static assets and handle case submissions."""

    server_version = "CaseServer/0.1"

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        directory = directory or str(ROOT_DIR)
        super().__init__(*args, directory=directory, **kwargs)

    # Map root to mock form
    def do_GET(self) -> None:  # noqa: N802 - part of http.server API
        if self.path == "/":
            self.path = "/ui/mock_form.html"
        if self.path == "/api/cases":
            self._handle_list_cases()
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - part of http.server API
        if self.path == "/api/cases":
            self._handle_create_case()
            return
        if self.path == "/api/upload":
            self._handle_upload()
            return
        if self.path == "/api/reset":
            self._handle_reset()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unsupported endpoint")

    # --- helpers ---------------------------------------------------------

    def _handle_create_case(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        payload_bytes = self.rfile.read(length)
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON payload")
            return

        record = self._normalise_payload(payload)
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cases (
                        case_id,
                        reaction_reported_term,
                        meddra_level,
                        meddra_term_text,
                        meddra_code,
                        meddra_version,
                        onset_date,
                        seriousness,
                        suspect_drug,
                        dose_text,
                        outcome,
                        narrative,
                        raw_payload
                    ) VALUES (
                        :case_id,
                        :reaction_reported_term,
                        :meddra_level,
                        :meddra_term_text,
                        :meddra_code,
                        :meddra_version,
                        :onset_date,
                        :seriousness,
                        :suspect_drug,
                        :dose_text,
                        :outcome,
                        :narrative,
                        :raw_payload
                    )
                    """,
                    record,
                )
                conn.commit()
        except sqlite3.DatabaseError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"DB error: {exc}")
            return

        self.send_response(HTTPStatus.CREATED)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "saved"}).encode("utf-8"))

    def _handle_list_cases(self) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM cases ORDER BY case_id").fetchall()
        data = [dict(row) for row in rows]
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def _handle_upload(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        payload_bytes = self.rfile.read(length)
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON payload")
            return

        filename = str(payload.get("filename", "")).strip()
        content = payload.get("content")
        if not filename or not content:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing filename or content")
            return

        base64_data = content.split(",", 1)[-1]
        try:
            file_bytes = base64.b64decode(base64_data)
        except (ValueError, binascii.Error) as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, f"Invalid base64 data: {exc}")
            return

        suffix = Path(filename).suffix.lower()
        if suffix not in ExcelIngestor.SUPPORTED_EXTENSIONS:
            self.send_error(
                HTTPStatus.BAD_REQUEST,
                f"Unsupported file type '{suffix}'. Expected one of {ExcelIngestor.SUPPORTED_EXTENSIONS}.",
            )
            return

        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                tmp_path = Path(tmp.name)

            ingestor = ExcelIngestor()
            normalizer = RecordNormalizer()
            rows = ingestor.load_rows(tmp_path)
            normalized_rows = normalizer.normalize_rows(rows)
            records = records_from_iterable(normalized_rows)
            payload_records = [self._record_to_payload(record) for record in records]
        except Exception as exc:  # pragma: no cover - runtime failure path
            self.send_error(HTTPStatus.BAD_REQUEST, f"Failed to process file: {exc}")
            return
        finally:
            if tmp_path:
                tmp_path.unlink(missing_ok=True)

        response = {
            "filename": filename,
            "count": len(payload_records),
            "records": payload_records[:200],
        }
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

    def _record_to_payload(self, record: CaseRecord) -> Dict[str, Any]:
        return {
            "case_id": record.case_id,
            "reaction_reported_term": record.reaction_reported_term,
            "meddra_level": record.meddra_level,
            "meddra_term_text": record.meddra_term_text,
            "meddra_code": record.meddra_code,
            "meddra_version": record.meddra_version,
            "onset_date": record.onset_date.isoformat() if record.onset_date else None,
            "seriousness": record.seriousness,
            "suspect_drug": record.suspect_drug,
            "dose_text": record.dose_text,
            "outcome": record.outcome,
            "narrative": record.narrative,
            "raw_payload": record.raw_payload,
        }

    def _handle_reset(self) -> None:
        """Testing helper: clear all rows from the DB."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("DELETE FROM cases")
                conn.commit()
        except sqlite3.DatabaseError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"DB reset error: {exc}")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "reset"}).encode("utf-8"))

    def _normalise_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_payload = payload.get("raw_payload", payload)
        if isinstance(raw_payload, dict):
            raw_payload_str = json.dumps(raw_payload, ensure_ascii=False)
        else:
            raw_payload_str = json.dumps({"value": raw_payload}, ensure_ascii=False)

        record = {
            "case_id": str(payload.get("case_id", "")).strip(),
            "reaction_reported_term": payload.get("reaction_reported_term"),
            "meddra_level": payload.get("meddra_level"),
            "meddra_term_text": payload.get("meddra_term_text"),
            "meddra_code": payload.get("meddra_code"),
            "meddra_version": payload.get("meddra_version"),
            "onset_date": payload.get("onset_date"),
            "seriousness": payload.get("seriousness"),
            "suspect_drug": payload.get("suspect_drug"),
            "dose_text": payload.get("dose_text"),
            "outcome": payload.get("outcome"),
            "narrative": payload.get("narrative"),
            "raw_payload": raw_payload_str,
        }
        return record


def run_server(port: int = 8000) -> None:
    init_db()
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, CaseRequestHandler)
    print(f"Serving on http://localhost:{port}")
    httpd.serve_forever()


if __name__ == "__main__":  # pragma: no cover - CLI entry
    run_server()
