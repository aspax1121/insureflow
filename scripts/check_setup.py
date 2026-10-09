"""Read-only project checks; SQLite is exercised only in memory."""

from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FOLDERS = (
    "frontend", "backend", "agents", "data/customers", "data/policies",
    "data/historical_claims", "data/claim_documents", "data/rules",
    "data/test_cases", "knowledge_base", "workflows", "evaluation", "docs",
    "tests", "scripts",
)


def main() -> int:
    checks = [("Python 3.11 or newer", sys.version_info >= (3, 11))]
    checks.extend((f"Folder: {name}", (ROOT / name).is_dir()) for name in REQUIRED_FOLDERS)
    try:
        connection = sqlite3.connect(":memory:")
        try:
            checks.append(("SQLite in-memory query", connection.execute("SELECT 1").fetchone() == (1,)))
        finally:
            connection.close()
    except sqlite3.Error as error:
        print(f"SQLite check error: {error}")
        checks.append(("SQLite in-memory query", False))
    print(f"Project: {ROOT}")
    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {label}")
    print("Foundation checks only; claims processing is not implemented yet.")
    return 0 if all(passed for _, passed in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
