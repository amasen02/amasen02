"""Refresh only the marked contribution region in a profile README."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from .core import RefreshError, Source, now, verified_prs

BEGIN = "<!-- BEGIN AUTO-CONTRIBUTIONS -->"
END = "<!-- END AUTO-CONTRIBUTIONS -->"
CANONICAL_USERNAME = "amasen02"


def _validate_username(username: str) -> str:
    if username != CANONICAL_USERNAME:
        raise RefreshError("contribution refresh requires the canonical amasen02 GitHub account")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username):
        raise RefreshError("contribution refresh username is malformed")
    return username


def _marker_region(raw: bytes) -> tuple[list[str], int, int, str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RefreshError("README must be UTF-8") from exc
    lines = text.splitlines(keepends=True)
    begin = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == BEGIN]
    end = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == END]
    if len(begin) != 1 or len(end) != 1 or begin[0] >= end[0]:
        raise RefreshError("README must contain exactly one ordered pair of contribution markers")
    newline = "\r\n" if lines[begin[0]].endswith("\r\n") else "\n"
    return lines, begin[0], end[0], newline


def _render(contributions: list[dict], coverage: dict) -> str:
    from . import presentation

    renderer = getattr(presentation, "render_contributions", None)
    if not callable(renderer):
        raise RefreshError("profile presentation has no contribution renderer")
    return renderer(contributions, coverage)


def _replace_region(raw: bytes, rendered: str) -> bytes:
    lines, begin, end, newline = _marker_region(raw)
    body = rendered.strip("\n").replace("\n", newline)
    replacement = [newline + body + newline + newline] if body else [newline]
    return "".join([*lines[: begin + 1], *replacement, *lines[end:]]).encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_receipt(path: Path | None, receipt: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, (json.dumps(receipt, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def _same_path(left: Path, right: Path | None) -> bool:
    return right is not None and left.resolve() == right.resolve()


def refresh(readme: Path, username: str, offline: Path | None = None, receipt_path: Path | None = None) -> dict:
    username = _validate_username(username)
    if _same_path(readme, receipt_path):
        raise RefreshError("receipt path must not be the README path")
    before = readme.read_bytes()
    _marker_region(before)
    source = Source(offline)
    contributions, coverage = verified_prs(source, username)
    rendered = _render(contributions, coverage)
    after = _replace_region(before, rendered)
    changed = after != before
    if changed:
        if readme.read_bytes() != before:
            raise RefreshError("README changed during contribution refresh")
        _atomic_write(readme, after)
    receipt = {
        "content_hash": hashlib.sha256(after).hexdigest(),
        "source_timestamp": source.evidence_at,
        "coverage": coverage,
        "newcount": len(contributions),
        "changed": changed,
        "source_urls": source.urls,
        "recorded_at": now(),
    }
    _write_receipt(receipt_path, receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh a marked profile contribution block")
    parser.add_argument("--username", required=True)
    parser.add_argument("--readme", required=True, type=Path)
    parser.add_argument("--offline", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        result = refresh(args.readme, args.username, args.offline, args.receipt)
    except (OSError, RefreshError) as exc:
        if not _same_path(args.readme, args.receipt):
            _write_receipt(args.receipt, {"status": "failed", "error": str(exc), "recorded_at": now()})
        print(f"contribution refresh failed: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
