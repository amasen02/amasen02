import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / ".github" / "criticality" / "summarize.py"
SPEC = importlib.util.spec_from_file_location("criticality_summary", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


HEADERS = ["repo.url", *MODULE.REQUIRED_SIGNALS, "default_score"]
SIGNALS = {
    signal: "1" for signal in MODULE.REQUIRED_SIGNALS
}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


class CriticalitySummaryTests(unittest.TestCase):
    def test_exact_threshold_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected.txt"
            expected.write_text("https://github.com/amasen02/below\nhttps://github.com/amasen02/at\n", encoding="utf-8")
            csv_path = root / "results.csv"
            write_csv(
                csv_path,
                [
                    {"repo.url": "https://github.com/amasen02/below", **SIGNALS, "default_score": "0.39999"},
                    {"repo.url": "https://github.com/amasen02/at", **SIGNALS, "default_score": "0.4"},
                ],
            )
            result = MODULE.summarize(csv_path, expected)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["qualified_urls"], ["https://github.com/amasen02/at"])
            statuses = {record["url"]: record["qualification_status"] for record in result["records"]}
            self.assertEqual(statuses["https://github.com/amasen02/below"], "BELOW_THRESHOLD")
            self.assertEqual(statuses["https://github.com/amasen02/at"], "THRESHOLD_MET")

    def test_missing_row_is_unknown_and_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected.txt"
            expected.write_text("https://github.com/amasen02/missing\n", encoding="utf-8")
            csv_path = root / "results.csv"
            write_csv(csv_path, [])
            result = MODULE.summarize(csv_path, expected)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["records"][0]["score"], None)
            self.assertEqual(result["records"][0]["qualification_status"], "UNKNOWN")
            self.assertTrue(any("missing CSV row" in error for error in result["errors"]))

    def test_invalid_signal_is_unknown_and_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected.txt"
            expected.write_text("https://github.com/amasen02/invalid\n", encoding="utf-8")
            csv_path = root / "results.csv"
            row = {"repo.url": "https://github.com/amasen02/invalid", **SIGNALS, "default_score": "0.8"}
            row["legacy.contributor_count"] = "NaN"
            write_csv(csv_path, [row])
            result = MODULE.summarize(csv_path, expected)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["records"][0]["score"], None)
            self.assertEqual(result["records"][0]["qualification_status"], "UNKNOWN")
            self.assertTrue(any("invalid numeric signal" in error for error in result["errors"]))

    def test_duplicate_row_replaces_valid_score_with_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected.txt"
            expected.write_text("https://github.com/amasen02/duplicate\n", encoding="utf-8")
            csv_path = root / "results.csv"
            row = {"repo.url": "https://github.com/amasen02/duplicate", **SIGNALS, "default_score": "0.8"}
            write_csv(csv_path, [row, row])
            result = MODULE.summarize(csv_path, expected)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["records"][0]["score"], None)
            self.assertEqual(result["records"][0]["qualification_status"], "UNKNOWN")
            self.assertEqual(result["qualified_urls"], [])

    def test_empty_expected_targets_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected.txt"
            expected.write_text("\n", encoding="utf-8")
            csv_path = root / "results.csv"
            write_csv(csv_path, [])
            result = MODULE.summarize(csv_path, expected)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("expected target set is empty", result["errors"])


if __name__ == "__main__":
    unittest.main()
