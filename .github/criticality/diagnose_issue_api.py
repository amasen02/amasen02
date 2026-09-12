#!/usr/bin/env python3
"""Retain sanitized first-page metadata from one GitHub issues API request."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def diagnose(raw_path: Path, output_path: Path, repo: str, since: str, captured_at: str, exit_code: int, error_path: Path) -> dict:
    raw = raw_path.read_text(encoding="utf-8", errors="replace")
    response_status = None
    last_page = None
    next_page_present = False
    first_page_count = None
    total_count = None
    body = ""
    for separator in ("\r\n\r\n", "\n\n"):
        if separator in raw:
            header_text, body = raw.split(separator, 1)
            break
    else:
        header_text = raw
    status_match = re.search(r"^HTTP/[^ ]+\s+(\d{3})", header_text, re.MULTILINE)
    if status_match:
        response_status = int(status_match.group(1))
    link_match = re.search(r"[?&]page=(\d+)[^>]*>;\s*rel=\"last\"", header_text)
    if link_match:
        last_page = int(link_match.group(1))
    next_page_present = bool(re.search(r"rel=\"next\"", header_text))
    try:
        items = json.loads(body)
        if isinstance(items, list):
            first_page_count = len(items)
            total_count = last_page if last_page is not None else (None if next_page_present else first_page_count)
            latest_number = items[0].get("number") if items and isinstance(items[0], dict) else None
        else:
            latest_number = None
    except json.JSONDecodeError:
        latest_number = None
    error = error_path.read_text(encoding="utf-8", errors="replace").strip()
    return {
        "repository": f"amasen02/{repo}",
        "request": f"GET /repos/amasen02/{repo}/issues?state=all&since={since}&per_page=1",
        "captured_at_utc": captured_at,
        "exit_code": exit_code,
        "response_status": response_status,
        "link_last_page": last_page,
        "link_next_present": next_page_present,
        "first_page_count": first_page_count,
        "total_count": total_count,
        "latest_number": latest_number,
        "error": error[:500] if error else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--since", required=True)
    parser.add_argument("--captured-at", required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--error-file", type=Path, required=True)
    args = parser.parse_args()
    entries = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else []
    entries.append(diagnose(args.raw, args.output, args.repo, args.since, args.captured_at, args.exit_code, args.error_file))
    args.output.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
