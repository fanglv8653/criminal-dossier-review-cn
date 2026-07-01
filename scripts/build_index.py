#!/usr/bin/env python3
"""Build page/material CSV indexes and an SQLite FTS database from OCR text."""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from pathlib import Path


MATERIAL_PATTERNS = [
    ("犯罪嫌疑人/被告人供述和辩解", re.compile(r"讯问笔录|供述|辩解|犯罪嫌疑人|被告人")),
    ("证人证言", re.compile(r"询问笔录|证人证言|证人")),
    ("被害人陈述", re.compile(r"被害人陈述|被害人")),
    ("鉴定意见", re.compile(r"鉴定意见|鉴定书|检验报告|检验鉴定")),
    ("物证", re.compile(r"物证|扣押.*物品|提取笔录|封存")),
    ("书证", re.compile(r"书证|银行流水|户籍|合同|账册|调取证据通知书")),
    ("勘验、检查、辨认、侦查实验等笔录", re.compile(r"勘验|检查笔录|辨认笔录|侦查实验|搜查笔录")),
    ("视听资料、电子数据", re.compile(r"电子数据|视听资料|聊天记录|微信|手机|光盘|监控|录像")),
]


def detect_category(text: str) -> str:
    for category, pattern in MATERIAL_PATTERNS:
        if pattern.search(text):
            return category
    return "待分类"


def load_manifest(case_dir: Path) -> list[dict]:
    with (case_dir / "00_manifest" / "manifest.csv").open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", required=True)
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    text_dir = case_dir / "04_ocr_text"
    index_dir = case_dir / "05_index"
    index_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(case_dir)

    page_rows = []
    material_rows = []
    for file_index, row in enumerate(manifest, 1):
        try:
            pages = int(row["pages"])
        except Exception:
            pages = 0
        current_material = None
        for page in range(1, pages + 1):
            stem = f"f{file_index:04d}_p{page:05d}"
            txt_path = text_dir / f"{stem}.txt"
            text = txt_path.read_text(encoding="utf-8", errors="replace") if txt_path.exists() else ""
            category = detect_category(text)
            dossier_page = ""
            m = re.search(r"(?:第\s*)?(\d{1,5})\s*(?:页|PAGE)", text[:500], re.IGNORECASE)
            if m:
                dossier_page = m.group(1)
            page_rows.append(
                {
                    "file_id": f"f{file_index:04d}",
                    "source_path": row["source_path"],
                    "file_name": row["file_name"],
                    "pdf_page": page,
                    "dossier_page_candidate": dossier_page,
                    "ocr_status": "done" if txt_path.exists() else "missing",
                    "text_path": str(txt_path) if txt_path.exists() else "",
                    "detected_material_type": category,
                    "needs_original_review": "yes" if category != "待分类" else "",
                    "notes": "",
                }
            )
            if category != "待分类" and category != current_material:
                material_rows.append(
                    {
                        "material_name": text.splitlines()[0][:80] if text.splitlines() else category,
                        "legal_evidence_category": category,
                        "file_name": row["file_name"],
                        "source_path": row["source_path"],
                        "start_pdf_page": page,
                        "dossier_page_candidate": dossier_page,
                        "ocr_status": "done" if txt_path.exists() else "missing",
                        "original_review_status": "pending",
                        "notes": "auto-detected",
                    }
                )
                current_material = category

    pages_csv = index_dir / "pages.csv"
    with pages_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "file_id",
            "source_path",
            "file_name",
            "pdf_page",
            "dossier_page_candidate",
            "ocr_status",
            "text_path",
            "detected_material_type",
            "needs_original_review",
            "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(page_rows)

    materials_csv = index_dir / "materials.csv"
    with materials_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "material_name",
            "legal_evidence_category",
            "file_name",
            "source_path",
            "start_pdf_page",
            "dossier_page_candidate",
            "ocr_status",
            "original_review_status",
            "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(material_rows)

    db_path = index_dir / "search.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS pages")
    conn.execute("CREATE VIRTUAL TABLE pages USING fts5(file_name, source_path, pdf_page UNINDEXED, category, text)")
    for pr in page_rows:
        text = Path(pr["text_path"]).read_text(encoding="utf-8", errors="replace") if pr["text_path"] else ""
        conn.execute(
            "INSERT INTO pages(file_name, source_path, pdf_page, category, text) VALUES (?, ?, ?, ?, ?)",
            (pr["file_name"], pr["source_path"], pr["pdf_page"], pr["detected_material_type"], text),
        )
    conn.commit()
    conn.close()

    print(f"Wrote {pages_csv}, {materials_csv}, {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

