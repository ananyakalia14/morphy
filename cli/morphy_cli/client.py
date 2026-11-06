"""Shared HTTP client for the MORPHY engine."""

import os
from uuid import UUID
from urllib.parse import urlsplit
import httpx


class EngineError(Exception):
    """Error returned by the MORPHY engine with an actionable message."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


_STATUS_HINTS = {
    401: "Sign in again — your session may have expired.",
    403: "Access denied. Check your database permissions.",
    409: "An administrator must connect this database first.",
    413: "The input or result is too large. Narrow your query.",
    422: "Validation or generation failed. Try a simpler question.",
    502: "The database is unreachable. Check the connection.",
    503: "The engine or a required service is unavailable.",
}


class MorphyClient:
    """Thin wrapper around httpx for the MORPHY engine API."""

    def __init__(self, base_url: str, database: UUID | None = None):
        self.base_url = base_url
        self.database = database
        self.prefix = (
            f"/api/engine/databases/{database}" if database else "/api/sample"
        )
        headers = {}
        if database:
            token = os.getenv("MORPHY_ACCESS_TOKEN")
            if not token:
                raise SystemExit(
                    "Set MORPHY_ACCESS_TOKEN to your active Supabase session token."
                )
            endpoint = urlsplit(base_url)
            if endpoint.scheme != "https" and not (
                endpoint.scheme == "http"
                and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
            ):
                raise SystemExit(
                    "Use HTTPS or a loopback address for authenticated requests."
                )
            headers["Authorization"] = "Bearer " + token
        self._http = httpx.Client(
            base_url=base_url,
            timeout=195,
            headers=headers,
            follow_redirects=False,
        )

    def close(self):
        self._http.close()

    def _request(self, method: str, path: str, payload=None):
        if method == "GET":
            response = self._http.get(path)
        elif method == "POST":
            response = self._http.post(path, json=payload)
        elif method == "PUT":
            response = self._http.put(path, json=payload)
        else:
            raise ValueError(f"Unsupported method: {method}")

        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            hint = _STATUS_HINTS.get(response.status_code, "")
            message = str(detail)
            if hint and hint not in message:
                message = f"{message}\n{hint}"
            raise EngineError(response.status_code, message)
        return response.json()

    def health(self):
        return self._request("GET", "/api/health")

    def schema(self):
        return self._request("GET", self.prefix + "/schema")

    def generate(self, question: str):
        return self._request("POST", self.prefix + "/generate", {"question": question})

    def query(self, sql: str):
        return self._request("POST", self.prefix + "/query", {"sql": sql})

    @property
    def is_live(self) -> bool:
        return self.database is not None
