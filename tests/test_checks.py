import unittest

from docling_pipeline.checks import check_table, parse_number, summarize


class ParseNumberTests(unittest.TestCase):
    def test_cases(self):
        cases = {
            "$ 109,896": 109896.0,
            "109,896": 109896.0,
            "(180)": -180.0,
            "$ (1,226)": -1226.0,
            "36.1%": 36.1,
            "1,234.56": 1234.56,
            "1.234,56": 1234.56,
            "12,5": 12.5,
            "1.234.567": 1234567.0,
            "\u22123": -3.0,
            "-3": -3.0,
            "0": 0.0,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_number(text), expected)

    def test_not_numbers(self):
        for text in ["", "—", "-", "n/a", "abc", "Q1 2026", "12,34,56", None]:
            with self.subTest(text=text):
                self.assertIsNone(parse_number(text))


class CheckTableTests(unittest.TestCase):
    def test_good_table(self):
        result = check_table(["Item", "2025", "2026"], [["Revenue", "90,234", "109,896"]])
        self.assertTrue(result["ok"])
        self.assertEqual(result["numeric_ratio"], 1.0)

    def test_empty_table_is_flagged(self):
        result = check_table(["Item", "2025"], [])
        self.assertFalse(result["ok"])
        self.assertIn("no rows", result["issues"])

    def test_ragged_rows_are_flagged(self):
        result = check_table(["A", "B", "C"], [["x", "1"]])
        self.assertIn("ragged rows", result["issues"])

    def test_single_column_is_flagged(self):
        self.assertIn("fewer than 2 columns", check_table(["A"], [["x"]])["issues"])


class SummarizeTests(unittest.TestCase):
    def test_summary_counts(self):
        checks = [{"ok": True}, {"ok": False}]
        s = summarize(3, "# title", checks)
        self.assertEqual((s["pages"], s["tables"], s["tables_flagged"], s["ok"]), (3, 2, 1, True))

    def test_empty_markdown_is_not_ok(self):
        self.assertFalse(summarize(3, "   ", [])["ok"])
        self.assertFalse(summarize(0, "text", [])["ok"])


if __name__ == "__main__":
    unittest.main()
