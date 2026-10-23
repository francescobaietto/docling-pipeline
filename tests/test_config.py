import unittest

from docling_pipeline.config import Config, ConfigError


class ConfigTests(unittest.TestCase):
    def test_missing_required_variables(self):
        with self.assertRaises(ConfigError) as ctx:
            Config.from_env({})
        self.assertIn("N8N_BASE_URL", str(ctx.exception))
        self.assertIn("N8N_TOKEN", str(ctx.exception))

    def test_defaults_and_trailing_slash(self):
        cfg = Config.from_env({"N8N_BASE_URL": "https://n8n.example/webhook/", "N8N_TOKEN": "t"})
        self.assertEqual(cfg.n8n_base_url, "https://n8n.example/webhook")
        self.assertEqual(cfg.max_docs_per_run, 10)
        self.assertFalse(cfg.do_ocr)

    def test_overrides(self):
        cfg = Config.from_env(
            {"N8N_BASE_URL": "https://x", "N8N_TOKEN": "t", "MAX_DOCS_PER_RUN": "3", "DO_OCR": "true"}
        )
        self.assertEqual(cfg.max_docs_per_run, 3)
        self.assertTrue(cfg.do_ocr)

    def test_invalid_integer(self):
        with self.assertRaises(ConfigError):
            Config.from_env({"N8N_BASE_URL": "https://x", "N8N_TOKEN": "t", "MAX_PDF_MB": "abc"})
        with self.assertRaises(ConfigError):
            Config.from_env({"N8N_BASE_URL": "https://x", "N8N_TOKEN": "t", "MAX_PDF_MB": "0"})


if __name__ == "__main__":
    unittest.main()
