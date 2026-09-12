#!/usr/bin/env python3
"""Validate and summarize an official OpenSSF criticality-score CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse


THRESHOLD = Decimal("0.4")
PROFILE_URL = "https://github.com/amasen02/amasen02"
REQUIRED_SIGNALS = (
    "legacy.created_since",
    "legacy.updated_since",
    "legacy.contributor_count",
    "legacy.org_count",
    "legacy.commit_frequency",
    "legacy.recent_release_count",
    "legacy.updated_issues_count",
    "legacy.closed_issues_count",
    "legacy.issue_comment_frequency",
    "legacy.github_mention_count",
)


def canonical_url(value: str) -> str:
    """Return a canonical owner/repository URL, or raise ValueError."""

    parsed = urlparse(value.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != "github.com"
        or len(parts) != 2
        or any(part in {".", ".."} for part in parts)
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"invalid GitHub repository URL: {value!r}")
    url = f"https://github.com/{parts[0].lower()}/{parts[1].lower()}"
    if not url.startswith("https://github.com/amasen02/"):
        raise ValueError(f"repository owner must be amasen02: {value!r}")
    return url


def _decimal(value: str, field: str, *, nonnegative: bool = True) -> Decimal:
    if value is None or not value.strip():
        raise ValueError(f"missing required signal {field}")
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(f"invalid numeric signal {field}: {value!r}") from exc
    if not parsed.is_finite() or (nonnegative and parsed < 0):
        raise ValueError(f"invalid numeric signal {field}: {value!r}")
    return parsed


def summarize(csv_path: Path, expected_path: Path) -> dict:
    """Parse a raw official CSV and return a JSON-serializable audit result.

    Missing or invalid records are represented as UNKNOWN and also become
    errors.  This keeps an incomplete measurement from being interpreted as a
    zero score or as evidence that a repository failed the threshold.
    """

    errors: list[str] = []
    expected: list[str] = []
    expected_seen: set[str] = set()
    for line_number, line in enumerate(expected_path.read_text(encoding="utf-8").splitlines(), 1):
        value = line.strip()
        if not value:
            continue
        try:
            url = canonical_url(value)
        except ValueError as exc:
            errors.append(f"expected target line {line_number}: {exc}")
            continue
        if url in expected_seen:
            errors.append(f"duplicate expected target: {url}")
            continue
        expected_seen.add(url)
        expected.append(url)
    if not expected:
        errors.append("expected target set is empty")

    records: dict[str, dict] = {}
    try:
        with csv_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                errors.append("CSV is missing a header row")
            else:
                required_columns = ("repo.url", *REQUIRED_SIGNALS, "default_score")
                missing_columns = [column for column in required_columns if column not in reader.fieldnames]
                if missing_columns:
                    errors.append("CSV is missing required columns: " + ", ".join(missing_columns))
                if len(reader.fieldnames) != len(set(reader.fieldnames)):
                    errors.append("CSV header contains duplicate columns")

            for row_number, row in enumerate(reader, 2):
                raw_url = row.get("repo.url")
                try:
                    if None in row:
                        raise ValueError("CSV row has extra columns")
                    url = canonical_url(raw_url or "")
                    if url not in expected_seen:
                        raise ValueError(f"repository is outside the expected target set: {url}")
                    if url in records:
                        raise ValueError(f"duplicate CSV row for {url}")
                    for signal_name in REQUIRED_SIGNALS:
                        _decimal(row.get(signal_name, ""), signal_name)
                    score = _decimal(row.get("default_score", ""), "default_score")
                    if score > 1:
                        raise ValueError(f"invalid numeric signal default_score: {score!r}")
                    records[url] = {
                        "url": url,
                        "score": str(score),
                        "score_status": "MEASURED",
                    }
                except ValueError as exc:
                    errors.append(f"CSV row {row_number}: {exc}")
                    if raw_url:
                        try:
                            unknown_url = canonical_url(raw_url)
                        except ValueError:
                            unknown_url = raw_url.strip()
                        records[unknown_url] = {
                            "url": unknown_url,
                            "score": None,
                            "score_status": "UNKNOWN",
                            "reason": str(exc),
                        }
    except OSError as exc:
        errors.append(f"cannot read CSV: {exc}")

    for url in expected:
        if url not in records:
            records[url] = {
                "url": url,
                "score": None,
                "score_status": "UNKNOWN",
                "reason": "no CSV row was produced",
            }
            errors.append(f"missing CSV row: {url}")

    output_records = []
    qualified = []
    for url in expected:
        record = records[url]
        eligible = url != PROFILE_URL
        result = {
            **record,
            "qualification_eligible": eligible,
        }
        if record["score_status"] == "UNKNOWN":
            result["threshold_status"] = "UNKNOWN"
            result["qualification_status"] = "UNKNOWN"
        else:
            score = Decimal(record["score"])
            if score >= THRESHOLD:
                result["threshold_status"] = "THRESHOLD_MET"
                result["qualification_status"] = "INELIGIBLE_PROFILE_REPOSITORY" if not eligible else "NOT_ASSESSED"
                if eligible:
                    qualified.append(url)
            else:
                result["threshold_status"] = "BELOW_THRESHOLD"
                result["qualification_status"] = "BELOW_THRESHOLD"
        output_records.append(result)

    measured = sum(record["score_status"] == "MEASURED" for record in output_records)
    return {
        "threshold": str(THRESHOLD),
        "comparison": ">=",
        "expected_count": len(expected),
        "measured_count": measured,
        "coverage": (measured / len(expected)) if expected else 0.0,
        "threshold_met_count": len(qualified),
        "threshold_met_urls": qualified,
        "errors": errors,
        "records": output_records,
        "status": "PASS" if not errors else "FAIL",
    }


def render_summary(result: dict) -> str:
    lines = [
        "## OpenSSF criticality audit",
        "",
        "Official v2.0.4 CSV measurement using the unchanged `original_pike` defaults and `-depsdev-disable`.",
        "",
        f"Coverage: `{result['measured_count']}/{result['expected_count']}` rows ({result['coverage']:.6%}).",
        f"Qualification threshold: `default_score >= {result['threshold']}` (official CSV printed five-decimal value; no additional rounding). Near-threshold decisions require full-precision recalculation.",
    ]
    if result["threshold_met_urls"]:
        if result["status"] == "PASS":
            lines.extend(["", "Repositories whose measured score met the threshold:", ""])
            lines.extend(f"- `{url}`" for url in result["threshold_met_urls"])
        else:
            lines.extend(["", "Threshold results withheld because validation failed; no eligibility claim is made."])
    else:
        if result["status"] == "PASS":
            lines.extend(["", "Threshold result: **NO THRESHOLD MET** (no eligible repository reached 0.4).", "Measurement passed, but no software qualification is evidenced by this score alone."])
        else:
            lines.extend(["", "Threshold results withheld because validation failed; no eligibility claim is made."])
    unknown_count = sum(record["score_status"] == "UNKNOWN" for record in result["records"])
    if unknown_count:
        lines.extend(["", f"UNKNOWN records: `{unknown_count}`. Unknown values are excluded from qualification and cause the audit to fail."])
    if result["errors"]:
        lines.extend(["", "Validation errors:", ""])
        lines.extend(f"- {error}" for error in result["errors"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    args = parser.parse_args(argv)
    result = summarize(args.csv, args.expected)
    rendered = render_summary(result)
    if args.json_out:
        args.json_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.summary_out:
        args.summary_out.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
