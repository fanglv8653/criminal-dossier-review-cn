#!/usr/bin/env python3
"""Search the OCR SQLite index."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    db = Path(args.case_dir) / "05_index" / "search.sqlite"
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT file_name, pdf_page, category, snippet(pages, 4, '[', ']', '...', 12) "
        "FROM pages WHERE pages MATCH ? LIMIT ?",
        (args.query, args.limit),
    ).fetchall()
    conn.close()

    for file_name, pdf_page, category, snippet in rows:
        print(f"{file_name} | PDF页 {pdf_page} | {category}\n{snippet}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

