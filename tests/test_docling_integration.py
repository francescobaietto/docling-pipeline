"""Runs real Docling on the synthetic fixture. Heavy: skipped unless RUN_DOCLING_TESTS=1.

CI image builds and local runs with Docling installed can enable it:
    RUN_DOCLING_TESTS=1 python -m unittest tests.test_docling_integration
"""
import os
import unittest
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_table.pdf"


@unittest.skipUnless(os.environ.get("RUN_DOCLING_TESTS") == "1", "set RUN_DOCLING_TESTS=1 to run")
class DoclingIntegrationTests(unittest.TestCase):
    def test_extracts_text_and_table(self):
        from docling_pipeline.converter import DoclingConverter

        result = DoclingConverter(do_ocr=False).convert(str(FIXTURE))
        self.assertEqual(result.pages, 1)
        self.assertIn("Revenue", result.markdown)
        self.assertGreaterEqual(len(result.tables), 1)
        flat = " ".join(cell for row in result.tables[0].rows for cell in row)
        self.assertIn("109,896", flat)


if __name__ == "__main__":
    unittest.main()
