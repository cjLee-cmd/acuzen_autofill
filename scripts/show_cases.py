"""Print stored cases from the SQLite database."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "artifacts/mock_cases.db"


def fetch_cases() -> list[dict[str, str]]:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM cases ORDER BY case_id").fetchall()
    return [dict(row) for row in rows]


def main() -> int:
    cases = fetch_cases()
    if not cases:
        print("No cases stored yet. Run the server and submit a case first.")
        return 1

    for idx, case in enumerate(cases, start=1):
        print(f"[{idx}] case_id={case['case_id']}")
        print(json.dumps(case, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI utility
    raise SystemExit(main())
