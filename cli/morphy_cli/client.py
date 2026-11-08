"""Shared HTTP client for the MORPHY engine."""

import os
from typing import Any, Callable, Optional, Union
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
    413: "The input or result is too large. Narrow your query or CSV.",
    422: "Validation or generation failed. Check the SQL syntax or permitted schema.",
    502: "The database is unreachable. Check the connection and credentials.",
    503: "The engine or a required service is unavailable.",
}


class MorphyClient:
    """Thin wrapper around httpx for the MORPHY engine API."""

    def __init__(
        self,
        base_url: str,
        database: Optional[Union[UUID, str]] = None,
        token: Optional[Union[str, Callable[[], str]]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.database: Optional[UUID] = UUID(str(database)) if database else None
        self._token_source = token
        self._validate_endpoint(self.base_url)

        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=195.0,
            follow_redirects=False,
        )

    def _validate_endpoint(self, url: str) -> None:
        if self.database:
            endpoint = urlsplit(url)
            if endpoint.scheme != "https" and not (
                endpoint.scheme == "http"
                and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
            ):
                raise SystemExit(
                    "Use HTTPS or a loopback address for authenticated requests."
                )

    def _get_token(self) -> Optional[str]:
        if callable(self._token_source):
            try:
                return self._token_source()
            except Exception:
                return None
        if self._token_source:
            return str(self._token_source)
        return os.getenv("MORPHY_ACCESS_TOKEN")

    def set_token_source(self, source: Union[str, Callable[[], str], None]) -> None:
        self._token_source = source

    def set_database(self, database: Optional[Union[UUID, str]]) -> None:
        if database is None:
            self.database = None
        else:
            try:
                self.database = UUID(str(database))
            except ValueError:
                self.database = str(database)  # type: ignore
        self._validate_endpoint(self.base_url)

    @property
    def prefix(self) -> str:
        return f"/api/engine/databases/{self.database}" if self.database else "/api/sample"

    @property
    def is_live(self) -> bool:
        return self.database is not None

    def close(self) -> None:
        self._http.close()

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.database:
            token = self._get_token()
            if not token:
                raise SystemExit(
                    "Set MORPHY_ACCESS_TOKEN or run /login to authenticate live database queries."
                )
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Any] = None,
        content: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        req_headers = self._build_headers()
        if headers:
            req_headers.update(headers)

        try:
            if method == "GET":
                response = self._http.get(path, headers=req_headers)
            elif method == "POST":
                response = self._http.post(path, json=payload, headers=req_headers)
            elif method == "PUT":
                if content is not None:
                    response = self._http.put(path, content=content, headers=req_headers)
                else:
                    response = self._http.put(path, json=payload, headers=req_headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
        except httpx.ConnectError as err:
            raise EngineError(503, f"Cannot connect to engine at {self.base_url}. Service unavailable.") from err
        except httpx.TimeoutException as err:
            raise EngineError(504, "Engine request timed out.") from err
        except httpx.HTTPError as err:
            raise EngineError(500, f"HTTP communication failed: {err}") from err

        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            hint = _STATUS_HINTS.get(response.status_code, "")
            message = str(detail)
            if "suspended" in message.lower() or "suspension" in message.lower():
                hint = ""
            if hint and hint not in message:
                message = f"{message}\n{hint}"
            raise EngineError(response.status_code, message)
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/health")

    def schema(self) -> dict[str, Any]:
        return self._request("GET", self.prefix + "/schema")

    def generate(
        self,
        question: str,
        include_clarification: bool = False,
        require_template: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"question": question}
        if self.is_live:
            if include_clarification:
                payload["include_clarification"] = True
            if require_template:
                payload["require_template"] = True
        return self._request("POST", self.prefix + "/generate", payload=payload)

    def query(self, sql: str) -> dict[str, Any]:
        return self._request("POST", self.prefix + "/query", payload={"sql": sql})

    def connect_database(self, uri: str) -> dict[str, Any]:
        """Save and test PostgreSQL connection URI on the active database."""
        if not self.database:
            raise EngineError(400, "Select a database first using /use-db <id>")
        return self._request(
            "PUT",
            f"/api/engine/databases/{self.database}/connection",
            payload={"uri": uri},
        )

    def import_file(
        self, file_data: Union[str, bytes], is_parquet: bool = False
    ) -> dict[str, Any]:
        """Import UTF-8 CSV or Parquet data into the active SQLite/CSV database."""
        if not self.database:
            raise EngineError(400, "Select a database first using /use-db <id>")
        raw_bytes = file_data.encode("utf-8") if isinstance(file_data, str) else file_data
        if len(raw_bytes) > 1_048_576:
            raise EngineError(413, "Choose a CSV or Parquet file up to 1 MB.")
        content_type = (
            "application/vnd.apache.parquet"
            if is_parquet
            else "text/csv; charset=utf-8"
        )
        return self._request(
            "PUT",
            f"/api/engine/databases/{self.database}/import",
            content=raw_bytes,
            headers={"Content-Type": content_type},
        )

    def import_csv(
        self, csv_data: Union[str, bytes], is_parquet: bool = False
    ) -> dict[str, Any]:
        """Backward-compatible wrapper for import_file."""
        return self.import_file(csv_data, is_parquet=is_parquet)

    def render_panel(
        self, dashboard_id: Union[UUID, str], query_id: Union[UUID, str]
    ) -> dict[str, Any]:
        """Render a saved dashboard panel under the caller's RLS policy."""
        return self._request(
            "POST",
            f"/api/engine/dashboards/{dashboard_id}/panels/{query_id}/render",
        )
