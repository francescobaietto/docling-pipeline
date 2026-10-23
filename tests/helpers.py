import requests


class FakeTime:
    """Deterministic clock: sleeping advances time instantly."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeResponse:
    def __init__(self, status=200, data=None, chunks=None):
        self.status_code = status
        self._data = {} if data is None else data
        self._chunks = chunks or []
        self.closed = False

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1):
        yield from self._chunks

    def close(self):
        self.closed = True


class FakeSession:
    """Plays back scripted outcomes (responses or exceptions); the last one repeats."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def _next(self):
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self._next()

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)
