#!/usr/bin/env python3
"""Render PDF pages and OCR them through local Umi-OCR HTTP API."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


def post_json(url: str, payload: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def render_page(pdf: Path, page: int, out_png: Path, dpi: int) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    prefix = out_png.with_suffix("")
    cmd = [
        "pdftoppm",
        "-f",
        str(page),
        "-l",
        str(page),
        "-r",
        str(dpi),
        "-png",
        str(pdf),
        str(prefix),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    generated = prefix.parent / f"{prefix.name}-{page}.png"
    if generated.exists() and generated != out_png:
        generated.replace(out_png)
    if not out_png.exists():
        matches = sorted(prefix.parent.glob(f"{prefix.name}*.png"))
        if matches:
            matches[0].replace(out_png)
    if not out_png.exists():
        raise RuntimeError(f"pdftoppm did not create {out_png}")


def ocr_image(url: str, image_path: Path) -> dict:
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payloads = [
        {"base64": b64, "options": {"data.format": "dict"}},
        {"image": b64, "options": {"data.format": "dict"}},
        {"path": str(image_path), "options": {"data.format": "dict"}},
    ]
    last_error = None
    for payload in payloads:
        try:
            resp = post_json(url, payload)
            if isinstance(resp, dict):
                return resp
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
    raise RuntimeError(f"Umi-OCR request failed: {last_error}")


def extract_text(resp: dict) -> str:
    data = resp.get("data", resp)
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        parts = []
        for item in data:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p)
    if isinstance(data, dict):
        if isinstance(data.get("text"), str):
            return data["text"]
        if isinstance(data.get("raw"), str):
            return data["raw"]
        if isinstance(data.get("data"), str):
            return data["data"]
        return json.dumps(data, ensure_ascii=False)
    return json.dumps(resp, ensure_ascii=False)


def load_manifest(case_dir: Path) -> list[dict]:
    manifest = case_dir / "00_manifest" / "manifest.csv"
    with manifest.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--umi-url", default="http://127.0.0.1:1224/api/ocr")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--limit-pages", type=int, default=0, help="0 means no limit")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    pages_dir = case_dir / "02_pages"
    json_dir = case_dir / "03_ocr_json"
    text_dir = case_dir / "04_ocr_text"
    for d in (pages_dir, json_dir, text_dir):
        d.mkdir(parents=True, exist_ok=True)

    rows = load_manifest(case_dir)
    processed = 0
    failures = []
    for file_index, row in enumerate(rows, 1):
        if str(row.get("encrypted", "")).lower() in {"true", "yes"}:
            failures.append({"file": row["file_name"], "page": "", "error": "encrypted; provide working copy"})
            continue
        pdf = Path(row["source_path"])
        try:
            pages = int(row["pages"])
        except Exception:
            failures.append({"file": row["file_name"], "page": "", "error": "unknown page count"})
            continue
        for page in range(1, pages + 1):
            if args.limit_pages and processed >= args.limit_pages:
                break
            stem = f"f{file_index:04d}_p{page:05d}"
            img = pages_dir / f"{stem}.png"
            out_json = json_dir / f"{stem}.json"
            out_txt = text_dir / f"{stem}.txt"
            if out_json.exists() and out_txt.exists() and not args.overwrite:
                continue
            try:
                render_page(pdf, page, img, args.dpi)
                resp = ocr_image(args.umi_url, img)
                out_json.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
                out_txt.write_text(extract_text(resp), encoding="utf-8")
                processed += 1
            except Exception as exc:
                failures.append({"file": row["file_name"], "page": page, "error": str(exc)})
        if args.limit_pages and processed >= args.limit_pages:
            break

    fail_path = case_dir / "00_manifest" / "ocr_failures.csv"
    if failures:
        with fail_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["file", "page", "error"])
            writer.writeheader()
            writer.writerows(failures)
    print(f"OCR processed {processed} page(s). Failures: {len(failures)}")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

