#!/usr/bin/env python3
"""Scan a criminal dossier PDF folder without copying source PDFs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path


def sha1_head(path: Path, size: int = 1024 * 1024) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        h.update(f.read(size))
    return h.hexdigest()


def pdf_info_with_pypdf(path: Path) -> dict:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - dependency optional
        raise RuntimeError(f"pypdf unavailable: {exc}") from exc

    reader = PdfReader(str(path))
    encrypted = bool(reader.is_encrypted)
    pages = None
    text_layer = "unknown"
    if not encrypted:
        pages = len(reader.pages)
        sample = ""
        for page in reader.pages[: min(3, pages)]:
            try:
                sample += page.extract_text() or ""
            except Exception:
                pass
        text_layer = "yes" if sample.strip() else "no"
    return {"pages": pages, "encrypted": encrypted, "text_layer": text_layer, "method": "pypdf"}


def pdf_info_with_pdfinfo(path: Path) -> dict:
    result = subprocess.run(
        ["pdfinfo", str(path)],
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    out = result.stdout + result.stderr
    encrypted = "Encrypted:      yes" in out or "Incorrect password" in out
    pages = None
    for line in out.splitlines():
        if line.startswith("Pages:"):
            try:
                pages = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
    return {"pages": pages, "encrypted": encrypted, "text_layer": "unknown", "method": "pdfinfo"}


def scan_pdf(path: Path) -> dict:
    stat = path.stat()
    info = None
    error = ""
    for fn in (pdf_info_with_pypdf, pdf_info_with_pdfinfo):
        try:
            info = fn(path)
            break
        except Exception as exc:
            error = str(exc)
    if info is None:
        info = {"pages": None, "encrypted": "unknown", "text_layer": "unknown", "method": "failed"}
    return {
        "source_path": str(path.resolve()),
        "file_name": path.name,
        "size_bytes": stat.st_size,
        "modified_time": stat.st_mtime,
        "sha1_head": sha1_head(path),
        "pages": info["pages"] or "",
        "encrypted": info["encrypted"],
        "text_layer": info["text_layer"],
        "scan_method": info["method"],
        "ocr_status": "pending",
        "notes": error,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Original dossier folder or PDF path")
    parser.add_argument("--case-dir", required=True, help="Case workspace directory")
    args = parser.parse_args()

    source = Path(args.source)
    case_dir = Path(args.case_dir)
    manifest_dir = case_dir / "00_manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    pdfs = [source] if source.is_file() else sorted(source.rglob("*.pdf"))
    rows = [scan_pdf(p) for p in pdfs]

    csv_path = manifest_dir / "manifest.csv"
    fields = [
        "source_path",
        "file_name",
        "size_bytes",
        "modified_time",
        "sha1_head",
        "pages",
        "encrypted",
        "text_layer",
        "scan_method",
        "ocr_status",
        "notes",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    with (manifest_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Scanned {len(rows)} PDF(s). Manifest: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

