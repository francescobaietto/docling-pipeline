import unittest

import requests

from docling_pipeline.config import Config
from docling_pipeline.n8n_client import N8nClient, N8nError
from tests.helpers import FakeResponse, FakeSession, FakeTime


def make_client(outcomes, **cfg_overrides):
    cfg = Config(n8n_base_url="https://n8n.example/webhook", n8n_token="secret", **cfg_overrides)
    ft = FakeTime()
    session = FakeSession(outcomes)
    return N8nClient(cfg, session=session, sleep=ft.sleep, clock=ft.clock), session, ft


class WakeTests(unittest.TestCase):
    def test_retries_until_ready_and_sends_token(self):
        client, session, ft = make_client(
            [requests.ConnectionError(), requests.Timeout(), FakeResponse(200)]
        )
        client.wait_until_ready()
        self.assertEqual(ft.sleeps, [10, 10])
        method, url, kwargs = session.calls[-1]
        self.assertEqual((method, url), ("GET", "https://n8n.example/webhook/ping"))
        self.assertEqual(kwargs["headers"]["X-Pipeline-Token"], "secret")

    def test_gives_up_after_timeout(self):
        client, session, _ = make_client(
            [requests.ConnectionError()], wake_timeout_s=30, wake_interval_s=10
        )
        with self.assertRaises(N8nError):
            client.wait_until_ready()
        self.assertEqual(len(session.calls), 4)

    def test_bad_token_fails_fast(self):
        client, _, ft = make_client([FakeResponse(401)])
        with self.assertRaises(N8nError):
            client.wait_until_ready()
        self.assertEqual(ft.sleeps, [])


class PendingTests(unittest.TestCase):
    def test_filters_malformed_items(self):
        data = {"documents": [{"id": "a", "url": "https://x/a.pdf"}, {"id": "b"}, "junk"]}
        client, session, _ = make_client([FakeResponse(200, data)])
        self.assertEqual(client.pending(5), [{"id": "a", "url": "https://x/a.pdf"}])
        self.assertEqual(session.calls[0][2]["params"], {"limit": 5})

    def test_unexpected_payload(self):
        client, _, _ = make_client([FakeResponse(200, {"nope": 1})])
        with self.assertRaises(N8nError):
            client.pending(5)


class PostResultTests(unittest.TestCase):
    def test_retries_on_server_error(self):
        client, session, ft = make_client([FakeResponse(503), FakeResponse(200)])
        client.post_result({"kind": "document"})
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(ft.sleeps, [5])

    def test_client_error_is_not_retried(self):
        client, session, _ = make_client([FakeResponse(400)])
        with self.assertRaises(N8nError):
            client.post_result({"kind": "document"})
        self.assertEqual(len(session.calls), 1)

    def test_gives_up_after_three_attempts(self):
        client, session, _ = make_client([requests.ConnectionError()])
        with self.assertRaises(N8nError):
            client.post_result({"kind": "document"})
        self.assertEqual(len(session.calls), 3)


class StatusTests(unittest.TestCase):
    def test_polls_until_done(self):
        client, session, ft = make_client(
            [FakeResponse(200, {"done": False, "pending": 2}), FakeResponse(200, {"done": True, "failed": 0})]
        )
        status = client.wait_until_done("run1")
        self.assertTrue(status["done"])
        self.assertEqual(ft.sleeps, [60])
        self.assertEqual(session.calls[0][2]["params"], {"run_id": "run1"})

    def test_times_out(self):
        client, _, _ = make_client(
            [FakeResponse(200, {"done": False})], status_timeout_s=120, status_interval_s=60
        )
        with self.assertRaises(N8nError):
            client.wait_until_done("run1")

    def test_tolerates_transient_errors(self):
        client, _, _ = make_client([requests.ConnectionError(), FakeResponse(200, {"done": True})])
        self.assertTrue(client.wait_until_done("run1")["done"])


if __name__ == "__main__":
    unittest.main()
