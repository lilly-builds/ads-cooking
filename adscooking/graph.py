"""The only module that talks to the Meta Graph API.

Everything else builds payloads and hands them here, which is what makes the
whole kit testable: the tests swap this class for a fake and assert on the
payloads without a live ad account or a real token.

Two Meta behaviours are encoded here because both cost us hours to learn:

1. Page-owned endpoints (lead forms) need a *page* access token, not the
   system-user token. See `page_token()`.
2. When every call in a run fails with the generic error code 1, Meta is
   having an outage. The right response is to wait and re-run, not to
   regenerate tokens or rebuild the campaign. See `GraphError.is_transient`.
"""

from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid

DEFAULT_VERSION = "v21.0"
TIMEOUT_SECONDS = 30


def _encode_nested(params: dict) -> dict:
    """JSON-encode any nested value before it is form-encoded.

    Graph expects nested fields (targeting, object_story_spec, creative,
    promoted_object, asset_feed_spec) as JSON strings inside a form-encoded
    body. Handing urlencode a dict makes it call str() on it, which produces
    Python's repr with single quotes:

        targeting={'geo_locations': {'countries': ['US']}}

    Meta rejects that as an invalid parameter. Values that are already strings
    pass through untouched, so a field written as JSON in campaign.json still
    works.
    """
    return {
        key: json.dumps(value) if isinstance(value, (dict, list, bool)) else value
        for key, value in params.items()
    }


class GraphError(Exception):
    """An error Meta returned, parsed into something a caller can branch on."""

    def __init__(self, path: str, status: int, body: str):
        self.path = path
        self.status = status
        self.body = body
        parsed = {}
        try:
            parsed = json.loads(body).get("error", {})
        except (ValueError, AttributeError):
            pass
        self.code = parsed.get("code")
        self.subcode = parsed.get("error_subcode")
        self.message = parsed.get("message", body[:400])
        self.user_title = parsed.get("error_user_title")
        self.user_message = parsed.get("error_user_msg")
        super().__init__(f"{status} on {path}: {self.message}")

    @property
    def is_transient(self) -> bool:
        """Code 1 is Meta's generic 'something broke our end'.

        On its own it means little, but when every call in a run returns it,
        the account is not broken and the token is not expired: Meta is down.
        Callers should wait and re-run rather than change anything.
        """
        return self.code == 1

    @property
    def is_auth(self) -> bool:
        """190 is the expired or revoked token family."""
        return self.code == 190

    @property
    def is_permission(self) -> bool:
        """10 and 200 mean the token is valid but lacks the scope, or the asset
        was never assigned to the system user."""
        return self.code in (10, 200)

    def explain(self) -> str:
        """A human-readable next step, not just the raw message."""
        if self.is_auth:
            return (
                "The token is expired or was revoked. Generate a new one in Business "
                "Settings under Users, System users, and update your .env file."
            )
        if self.is_permission:
            return (
                "The token is valid but is not allowed to do this. Either a scope was "
                "missed when the token was generated, or the ad account or page was "
                "never assigned to the system user."
            )
        if self.is_transient:
            return (
                "Meta returned its generic error. If every call is failing this way, "
                "Meta is having an outage: wait an hour or two and re-run. Do not "
                "regenerate the token or rebuild the campaign."
            )
        return self.user_message or self.message


class Graph:
    """A thin Graph API client. No third-party dependencies by design."""

    def __init__(self, token: str, version: str = DEFAULT_VERSION):
        if not token:
            raise ValueError("Graph needs an access token")
        self._token = token
        self.version = version
        self.base = f"https://graph.facebook.com/{version}"

    # The token is deliberately private and has no accessor. Nothing in this
    # kit prints it, and keeping it off the instance surface means a stray
    # repr() or debug dump cannot leak it either.
    def __repr__(self) -> str:
        return f"<Graph {self.version}>"

    def get(self, path: str, **params):
        params["access_token"] = self._token
        url = f"{self.base}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"
        return self._send(urllib.request.Request(url, method="GET"), path)

    def post(self, path: str, params: dict, token: str | None = None):
        body = _encode_nested(params)
        body["access_token"] = token or self._token
        data = urllib.parse.urlencode(body).encode()
        url = f"{self.base}/{path.lstrip('/')}"
        return self._send(urllib.request.Request(url, data=data, method="POST"), path)

    def upload(self, path: str, field: str, file_path, extra: dict | None = None):
        """Multipart upload, used for /advideos and /adimages."""
        boundary = f"----adscooking{uuid.uuid4().hex}"
        fields = _encode_nested(extra or {})
        fields["access_token"] = self._token
        body = bytearray()

        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body.extend(f"{value}\r\n".encode())

        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        with open(file_path, "rb") as handle:
            content = handle.read()
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{field}"; '
            f'filename="{getattr(file_path, "name", str(file_path))}"\r\n'.encode()
        )
        body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
        body.extend(content)
        body.extend(f"\r\n--{boundary}--\r\n".encode())

        url = f"{self.base}/{path.lstrip('/')}"
        request = urllib.request.Request(url, data=bytes(body), method="POST")
        request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        return self._send(request, path)

    def debug_self(self) -> dict:
        """Inspect this token, including when it expires.

        /debug_token wants the token being inspected in `input_token`. There is
        no "current token" sentinel, so it has to be passed explicitly. This is
        the one place the token leaves the instance, and it goes to Meta only.
        """
        return self.get("debug_token", input_token=self._token)

    def page_token(self, page_id: str) -> str:
        """Lead form endpoints are page-owned and reject the system-user token.

        This exchange is easy to miss: publishing a campaign works fine right
        up until the lead form step, which then fails with a permission error
        that does not mention page tokens at all.
        """
        result = self.get(page_id, fields="access_token")
        token = result.get("access_token")
        if not token:
            raise GraphError(
                page_id,
                200,
                json.dumps(
                    {
                        "error": {
                            "code": 200,
                            "message": (
                                "No page access token came back. The system user needs "
                                "a task on this page, usually MANAGE or ADVERTISE."
                            ),
                        }
                    }
                ),
            )
        return token

    def _send(self, request, path: str):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise GraphError(path, exc.code, exc.read().decode()) from None
