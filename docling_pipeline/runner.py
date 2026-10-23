"""Entry point: wake n8n, fetch pending documents, convert, deliver, wait for n8n.

Logging policy: this repository is public, so logs must never contain document
content. Only ids, counts and durations are logged.
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
import time
import uuid
from dataclasses import asdict
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

import requests

from .checks import check_table, summarize
from .config import Config, ConfigError
from .converter import DoclingConverter
from .n8n_client import N8nClient, N8nError

log = logging.getLogger("docling_pipeline")


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("only absolute https URLs are accepted")


def download_pdf(url: str, dest: str, cfg: Config, session: Any) -> int:
    """Download a PDF with size limit and magic-bytes check. Returns the size in bytes."""
    validate_url(url)
    limit = cfg.max_pdf_mb * 1024 * 1024
    resp = session.get(url, stream=True, timeout=cfg.download_timeout_s)
    try:
        resp.raise_for_status()
        size = 0
        first = True
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                if first:
                    if not chunk.startswith(b"%PDF"):
                        raise ValueError("downloaded file is not a PDF")
                    first = False
                size += len(chunk)
                if size > limit:
                    raise ValueError("PDF exceeds the size limit")
                fh.write(chunk)
        if size == 0:
            raise ValueError("empty download")
        return size
    finally:
        resp.close()


def process_document(
    doc: Dict[str, str],
    *,
    cfg: Config,
    client: Any,
    converter: Any,
    run_id: str,
    session: Any,
) -> bool:
    doc_id = doc["id"]
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "input.pdf")
            size = download_pdf(doc["url"], path, cfg, session)
            converted = converter.convert(path)

        table_checks = [check_table(t.columns, t.rows) for t in converted.tables]
        summary = summarize(converted.pages, converted.markdown, table_checks)
        if not summary["ok"]:
            raise ValueError("conversion produced no content")
        summary.update(
            pdf_bytes=size,
            docling_version=converted.docling_version,
            duration_s=round(time.monotonic() - started, 1),
        )

        client.post_result(
            {
                "kind": "document",
                "run_id": run_id,
                "document_id": doc_id,
                "markdown": converted.markdown,
                "tables_expected": len(converted.tables),
                "metadata": summary,
            }
        )
        for table, check in zip(converted.tables, table_checks):
            client.post_result(
                {
                    "kind": "table",
                    "run_id": run_id,
                    "document_id": doc_id,
                    "table": asdict(table),
                    "check": check,
                }
            )
        log.info(
            "document %s delivered: pages=%s tables=%s flagged=%s",
            doc_id, summary["pages"], summary["tables"], summary["tables_flagged"],
        )
        return True
    except Exception as exc:  # boundary: one bad document must not stop the batch
        log.error("document %s failed: %s", doc_id, type(exc).__name__)
        try:
            client.post_result(
                {
                    "kind": "error",
                    "run_id": run_id,
                    "document_id": doc_id,
                    "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                }
            )
        except N8nError:
            log.error("could not report the failure of %s to n8n", doc_id)
        return False


def run(
    cfg: Config,
    client: Any,
    converter_factory: Callable[[], Any],
    session: Optional[Any] = None,
) -> int:
    session = session or requests.Session()
    run_id = uuid.uuid4().hex
    log.info("run %s started", run_id)
    try:
        client.wait_until_ready()
        docs = client.pending(cfg.max_docs_per_run)[: cfg.max_docs_per_run]
    except (N8nError, requests.RequestException) as exc:
        log.error("cannot talk to n8n: %s", type(exc).__name__)
        return 1
    if not docs:
        log.info("no documents to process")
        return 0

    converter = converter_factory()
    delivered = failures = 0
    for doc in docs:
        ok = process_document(
            doc, cfg=cfg, client=client, converter=converter, run_id=run_id, session=session
        )
        delivered += int(ok)
        failures += int(not ok)
    log.info("delivered=%d failed=%d", delivered, failures)

    if delivered:
        try:
            status = client.wait_until_done(run_id)
            n8n_failed = int(status.get("failed") or 0)
            if n8n_failed:
                log.error("n8n reported %d failed document(s)", n8n_failed)
                failures += n8n_failed
        except N8nError as exc:
            log.error("%s", exc)
            failures += 1
    return 1 if failures else 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        log.error("%s", exc)
        return 2
    client = N8nClient(cfg)
    return run(cfg, client, lambda: DoclingConverter(do_ocr=cfg.do_ocr))


if __name__ == "__main__":
    sys.exit(main())
