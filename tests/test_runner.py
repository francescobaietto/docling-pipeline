import os
import tempfile
import unittest
from unittest import mock

from docling_pipeline import runner
from docling_pipeline.config import Config
from docling_pipeline.converter import ConvertedDocument, ConvertedTable
from docling_pipeline.n8n_client import N8nError
from tests.helpers import FakeResponse, FakeSession

CFG = Config(n8n_base_url="https://n8n.example/webhook", n8n_token="t", max_pdf_mb=1)


class FakeClient:
    def __init__(self, docs=None, ready_error=None, status=None):
        self.docs = docs or []
        self.ready_error = ready_error
        self.status = status or {"done": True, "failed": 0}
        self.posts = []
        self.waited = False

    def wait_until_ready(self):
        if self.ready_error:
            raise self.ready_error

    def pending(self, limit):
        return self.docs

    def post_result(self, payload):
        self.posts.append(payload)

    def wait_until_done(self, run_id):
        self.waited = True
        return self.status


class FakeConverter:
    def __init__(self, fail=False):
        self.fail = fail

    def convert(self, path):
        if self.fail:
            raise RuntimeError("boom")
        table = ConvertedTable(0, 1, "cap", ["Item", "2026"], [["Revenue", "109,896"]])
        return ConvertedDocument("# Title\ntext", [table], pages=2, docling_version="x")


DOC = {"id": "doc1", "url": "https://example.com/a.pdf"}


class ValidateUrlTests(unittest.TestCase):
    def test_rejects_unsafe_urls(self):
        for url in ["http://example.com/a.pdf", "file:///etc/passwd", "ftp://x/a.pdf", "https://", "a.pdf"]:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    runner.validate_url(url)

    def test_accepts_https(self):
        runner.validate_url("https://example.com/a.pdf")


class DownloadTests(unittest.TestCase):
    def _download(self, chunks):
        resp = FakeResponse(200, chunks=chunks)
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "x.pdf")
            try:
                return runner.download_pdf("https://example.com/a.pdf", dest, CFG, FakeSession([resp]))
            finally:
                self.assertTrue(resp.closed)

    def test_ok(self):
        self.assertEqual(self._download([b"%PDF-1.4 ", b"data"]), 13)

    def test_not_a_pdf(self):
        with self.assertRaises(ValueError):
            self._download([b"<html>"])

    def test_too_large(self):
        with self.assertRaises(ValueError):
            self._download([b"%PDF" + b"0" * 700_000, b"0" * 700_000])

    def test_empty(self):
        with self.assertRaises(ValueError):
            self._download([])


class RunTests(unittest.TestCase):
    def test_nothing_to_do_never_builds_converter(self):
        factory = mock.Mock()
        self.assertEqual(runner.run(CFG, FakeClient(docs=[]), factory), 0)
        factory.assert_not_called()

    def test_n8n_unreachable(self):
        factory = mock.Mock()
        client = FakeClient(ready_error=N8nError("down"))
        self.assertEqual(runner.run(CFG, client, factory), 1)
        factory.assert_not_called()

    @mock.patch("docling_pipeline.runner.download_pdf", return_value=100)
    def test_success_delivers_document_then_tables_then_waits(self, _):
        client = FakeClient(docs=[DOC])
        code = runner.run(CFG, client, FakeConverter, session=object())
        self.assertEqual(code, 0)
        self.assertEqual([p["kind"] for p in client.posts], ["document", "table"])
        self.assertEqual(client.posts[0]["tables_expected"], 1)
        self.assertEqual(client.posts[0]["document_id"], "doc1")
        self.assertEqual(client.posts[0]["run_id"], client.posts[1]["run_id"])
        self.assertTrue(client.waited)

    @mock.patch("docling_pipeline.runner.download_pdf", return_value=100)
    def test_conversion_failure_reports_error_and_fails_run(self, _):
        client = FakeClient(docs=[DOC])
        code = runner.run(CFG, client, lambda: FakeConverter(fail=True), session=object())
        self.assertEqual(code, 1)
        self.assertEqual([p["kind"] for p in client.posts], ["error"])
        self.assertFalse(client.waited)

    @mock.patch("docling_pipeline.runner.download_pdf", return_value=100)
    def test_one_bad_document_does_not_stop_the_batch(self, _):
        class Flaky(FakeConverter):
            calls = 0

            def convert(self, path):
                Flaky.calls += 1
                if Flaky.calls == 1:
                    raise RuntimeError("boom")
                return super().convert(path)

        client = FakeClient(docs=[DOC, {"id": "doc2", "url": "https://example.com/b.pdf"}])
        code = runner.run(CFG, client, Flaky, session=object())
        self.assertEqual(code, 1)
        self.assertEqual([p["kind"] for p in client.posts], ["error", "document", "table"])
        self.assertTrue(client.waited)

    @mock.patch("docling_pipeline.runner.download_pdf", return_value=100)
    def test_n8n_reporting_failures_fails_run(self, _):
        client = FakeClient(docs=[DOC], status={"done": True, "failed": 1})
        self.assertEqual(runner.run(CFG, client, FakeConverter, session=object()), 1)

    @mock.patch("docling_pipeline.runner.download_pdf", return_value=100)
    def test_n8n_never_finishing_fails_run(self, _):
        client = FakeClient(docs=[DOC])
        client.wait_until_done = mock.Mock(side_effect=N8nError("timeout"))
        self.assertEqual(runner.run(CFG, client, FakeConverter, session=object()), 1)

    @mock.patch("docling_pipeline.runner.download_pdf", return_value=100)
    def test_empty_conversion_is_an_error(self, _):
        class Empty(FakeConverter):
            def convert(self, path):
                return ConvertedDocument("", [], pages=1)

        client = FakeClient(docs=[DOC])
        self.assertEqual(runner.run(CFG, client, Empty, session=object()), 1)
        self.assertEqual(client.posts[0]["kind"], "error")


if __name__ == "__main__":
    unittest.main()
