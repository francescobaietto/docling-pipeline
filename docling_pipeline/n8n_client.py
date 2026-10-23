from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

import requests

from .config import Config

log = logging.getLogger(__name__)


class N8nError(RuntimeError):
    """n8n is unreachable, rejected a request, or did not finish in time."""


class N8nClient:
    """Talks to the n8n webhooks described in docs/n8n-contract.md.

    The client is the *active* side: it wakes n8n up, asks what to do,
    delivers results and waits until n8n says it has finished.
    """

    def __init__(
        self,
        cfg: Config,
        session: Optional[Any] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cfg = cfg
        self.session = session or requests.Session()
        self._sleep = sleep
        self._clock = clock
        self._headers = {"X-Pipeline-Token": cfg.n8n_token}

    def _url(self, path: str) -> str:
        return f"{self.cfg.n8n_base_url.rstrip('/')}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs: Any):
        return self.session.request(
            method,
            self._url(path),
            headers=self._headers,
            timeout=self.cfg.request_timeout_s,
            **kwargs,
        )

    def wait_until_ready(self) -> None:
        """Ping n8n until it answers (a sleeping Render instance needs ~1 minute)."""
        deadline = self._clock() + self.cfg.wake_timeout_s
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._request("GET", "ping")
                if resp.status_code == 200:
                    log.info("n8n ready after %d attempt(s)", attempt)
                    return
                if resp.status_code in (401, 403):
                    raise N8nError("n8n rejected the token (check N8N_TOKEN)")
                log.info("n8n not ready yet (HTTP %s)", resp.status_code)
            except requests.RequestException as exc:
                log.info("n8n not reachable yet (%s)", type(exc).__name__)
            if self._clock() >= deadline:
                raise N8nError(f"n8n did not become ready within {self.cfg.wake_timeout_s}s")
            self._sleep(self.cfg.wake_interval_s)

    def pending(self, limit: int) -> List[Dict[str, str]]:
        resp = self._request("GET", "pending", params={"limit": limit})
        resp.raise_for_status()
        data = resp.json()
        docs = data.get("documents") if isinstance(data, dict) else None
        if not isinstance(docs, list):
            raise N8nError("unexpected payload from /pending")
        result: List[Dict[str, str]] = []
        for item in docs:
            if isinstance(item, dict) and item.get("id") and item.get("url"):
                result.append({"id": str(item["id"]), "url": str(item["url"])})
            else:
                log.warning("skipping malformed item in /pending")
        return result

    def post_result(self, payload: Dict[str, Any], retries: int = 3) -> None:
        last = "unknown"
        for attempt in range(1, retries + 1):
            try:
                resp = self._request("POST", "result", json=payload)
                if resp.status_code < 400:
                    return
                if resp.status_code < 500:
                    raise N8nError(f"n8n rejected the result (HTTP {resp.status_code})")
                last = f"HTTP {resp.status_code}"
            except requests.RequestException as exc:
                last = type(exc).__name__
            if attempt < retries:
                self._sleep(5 * attempt)
        raise N8nError(f"could not deliver result after {retries} attempts ({last})")

    def wait_until_done(self, run_id: str) -> Dict[str, Any]:
        """Poll /status until n8n reports it finished processing this run.

        Polling also keeps a free-tier n8n instance awake while it works.
        """
        deadline = self._clock() + self.cfg.status_timeout_s
        while True:
            try:
                resp = self._request("GET", "status", params={"run_id": run_id})
                resp.raise_for_status()
                status = resp.json()
                if isinstance(status, dict) and status.get("done") is True:
                    return status
                pending = status.get("pending") if isinstance(status, dict) else None
                log.info("waiting for n8n (pending=%s)", pending)
            except (requests.RequestException, ValueError) as exc:
                log.info("status check failed (%s)", type(exc).__name__)
            if self._clock() >= deadline:
                raise N8nError(f"n8n did not finish within {self.cfg.status_timeout_s}s")
            self._sleep(self.cfg.status_interval_s)
