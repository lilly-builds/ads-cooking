"""An in-memory Meta Graph API.

Same interface as adscooking.graph.Graph, so the workflows cannot tell the
difference. Every call is recorded, which lets the tests assert on the exact
payloads that would go to Meta without a token, an ad account, or a network.

It is deliberately strict: an unexpected write raises. That is what makes
`test_pulse_never_writes` meaningful rather than decorative.
"""

from __future__ import annotations

import json

from adscooking.graph import GraphError


class FakeGraph:
    def __init__(self, responses: dict | None = None, allow_writes: bool = True):
        self.responses = responses or {}
        self.allow_writes = allow_writes
        self.gets: list[tuple[str, dict]] = []
        self.posts: list[tuple[str, dict, str | None]] = []
        self.uploads: list[tuple[str, str, str]] = []
        self._counter = 0

    def _next_id(self, prefix: str = "id") -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    def get(self, path, **params):
        self.gets.append((path, params))
        for pattern, response in self.responses.items():
            if pattern == path or path.endswith(pattern):
                return response
        return {"id": self._next_id("get")}

    def post(self, path, params, token=None):
        if not self.allow_writes:
            raise AssertionError(f"This code must not write, but it POSTed to {path}")
        self.posts.append((path, params, token))
        return {"id": self._next_id("post")}

    def upload(self, path, field, file_path, extra=None):
        if not self.allow_writes:
            raise AssertionError(f"This code must not write, but it uploaded to {path}")
        self.uploads.append((path, field, str(file_path)))
        if path.endswith("/adimages"):
            # Meta nests the hash under a filename of its choosing, and sends no
            # top-level "hash". A fake that returns a friendlier shape than the
            # real API is a fake that hides bugs.
            return {"images": {"chosen_by_meta.jpg": {"hash": "fake-hash",
                                                      "url": "https://example.invalid/i.jpg"}}}
        return {"id": self._next_id("upload")}

    def page_token(self, page_id):
        self.gets.append((f"{page_id}:page_token", {}))
        return "fake-page-token"

    # Helpers the tests read
    def posted_to(self, suffix: str) -> list[dict]:
        return [params for path, params, _ in self.posts if path.endswith(suffix)]

    def token_used_for(self, suffix: str):
        for path, _, token in self.posts:
            if path.endswith(suffix):
                return token
        return None


def http_error(code: int, message: str = "boom", status: int = 400) -> GraphError:
    return GraphError("some/path", status, json.dumps({"error": {"code": code, "message": message}}))
