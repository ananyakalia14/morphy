"""Authentication and session management for MORPHY CLI using Supabase Auth and OS keyring."""

import json
import os
from pathlib import Path
import time
from typing import Any, Optional
import httpx
import keyring

CONFIG_DIR = Path.home() / ".morphy"
CONFIG_FILE = CONFIG_DIR / "config.json"
FALLBACK_TOKEN_FILE = CONFIG_DIR / ".tokens"
KEYRING_SERVICE = "morphy-cli"


class AuthError(Exception):
    """Authentication or session error with user-actionable message."""
    pass


class Session:
    """Holds authenticated session details."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        user_id: str,
        email: str,
        expires_at: float,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.user_id = user_id
        self.email = email
        self.expires_at = expires_at

    @property
    def is_expired(self) -> bool:
        """Returns True if the access token has expired or is expiring in <= 60s."""
        return time.time() >= (self.expires_at - 60)

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "user_id": self.user_id,
            "email": self.email,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            user_id=data["user_id"],
            email=data["email"],
            expires_at=data["expires_at"],
        )


def load_config() -> tuple[str, str]:
    """Load Supabase URL and anon key from env vars or ~/.morphy/config.json."""
    url = os.getenv("MORPHY_SUPABASE_URL")
    key = os.getenv("MORPHY_SUPABASE_ANON_KEY") or os.getenv("MORPHY_SUPABASE_PUBLIC_KEY")

    if not url or not key:
        if CONFIG_FILE.is_file():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                url = url or data.get("supabase_url")
                key = key or data.get("supabase_anon_key")
            except Exception:
                pass

    url = (url or "http://127.0.0.1:54321").rstrip("/")
    key = key or ""
    return url, key


def save_config(supabase_url: str, supabase_anon_key: str) -> None:
    """Save Supabase configuration to ~/.morphy/config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "supabase_url": supabase_url.rstrip("/"),
        "supabase_anon_key": supabase_anon_key,
    }
    CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AuthManager:
    """Manages Supabase sessions, token refreshing, and OS credential storage."""

    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        cfg_url, cfg_key = load_config()
        self.supabase_url = (supabase_url or cfg_url).rstrip("/")
        self.supabase_key = supabase_key if supabase_key is not None else cfg_key
        self.current_session: Optional[Session] = None
        self._keyring_key = f"refresh:{self.supabase_url}"

    def _headers(self) -> dict[str, str]:
        headers = {"apikey": self.supabase_key}
        if self.current_session and self.current_session.access_token:
            headers["Authorization"] = f"Bearer {self.current_session.access_token}"
        return headers

    def _store_refresh_token(self, refresh_token: str, session: Session) -> None:
        stored = False
        try:
            keyring.set_password(KEYRING_SERVICE, self._keyring_key, refresh_token)
            stored = True
        except Exception:
            stored = False

        # Fallback file if keyring fails (e.g. headless CI or container)
        if not stored:
            try:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                FALLBACK_TOKEN_FILE.write_text(
                    json.dumps(session.to_dict()),
                    encoding="utf-8"
                )
                try:
                    os.chmod(FALLBACK_TOKEN_FILE, 0o600)
                except Exception:
                    pass
            except Exception:
                pass

    def _get_stored_refresh_token(self) -> Optional[str]:
        try:
            token = keyring.get_password(KEYRING_SERVICE, self._keyring_key)
            if token:
                return token
        except Exception:
            pass

        if FALLBACK_TOKEN_FILE.is_file():
            try:
                data = json.loads(FALLBACK_TOKEN_FILE.read_text(encoding="utf-8"))
                return data.get("refresh_token")
            except Exception:
                pass
        return None

    def _clear_stored_tokens(self) -> None:
        try:
            keyring.delete_password(KEYRING_SERVICE, self._keyring_key)
        except Exception:
            pass

        if FALLBACK_TOKEN_FILE.is_file():
            try:
                FALLBACK_TOKEN_FILE.unlink(missing_ok=True)
            except Exception:
                pass

    def login(self, email: str, password: str) -> Session:
        """Authenticate with Supabase GoTrue using email and password."""
        if not self.supabase_key:
            raise AuthError(
                "Supabase Anon Key is not configured. Set MORPHY_SUPABASE_ANON_KEY or run config."
            )

        endpoint = f"{self.supabase_url}/auth/v1/token?grant_type=password"
        payload = {"email": email, "password": password}

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(endpoint, json=payload, headers={"apikey": self.supabase_key})
        except httpx.HTTPError as exc:
            raise AuthError(f"Network error during authentication: {exc}")

        if res.status_code != 200:
            try:
                err_data = res.json()
                detail = err_data.get("msg") or err_data.get("error_description") or res.text
            except Exception:
                detail = res.text
            raise AuthError(f"Login failed ({res.status_code}): {detail}")

        data = res.json()
        expires_in = data.get("expires_in", 3600)
        user_info = data.get("user", {})

        session = Session(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            user_id=user_info.get("id", ""),
            email=user_info.get("email", email),
            expires_at=time.time() + expires_in,
        )
        self.current_session = session
        self._store_refresh_token(session.refresh_token, session)
        return session

    def refresh(self) -> Session:
        """Refresh current session using refresh token."""
        refresh_token = (
            self.current_session.refresh_token
            if self.current_session
            else self._get_stored_refresh_token()
        )
        if not refresh_token:
            raise AuthError("No active session or refresh token found. Please /login.")

        endpoint = f"{self.supabase_url}/auth/v1/token?grant_type=refresh_token"
        payload = {"refresh_token": refresh_token}

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(endpoint, json=payload, headers={"apikey": self.supabase_key})
        except httpx.HTTPError as exc:
            raise AuthError(f"Network error during token refresh: {exc}")

        if res.status_code != 200:
            self._clear_stored_tokens()
            self.current_session = None
            raise AuthError("Session expired or refresh token invalid. Please /login again.")

        data = res.json()
        expires_in = data.get("expires_in", 3600)
        user_info = data.get("user", {})

        session = Session(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            user_id=user_info.get("id", self.current_session.user_id if self.current_session else ""),
            email=user_info.get("email", self.current_session.email if self.current_session else ""),
            expires_at=time.time() + expires_in,
        )
        self.current_session = session
        self._store_refresh_token(session.refresh_token, session)
        return session

    def restore_session(self) -> Optional[Session]:
        """Attempt to restore or refresh a session from saved token."""
        env_token = os.getenv("MORPHY_ACCESS_TOKEN")
        if env_token:
            self.current_session = Session(
                access_token=env_token,
                refresh_token="",
                user_id="",
                email="",
                expires_at=time.time() + 86400,
            )
            return self.current_session

        refresh_token = self._get_stored_refresh_token()
        if not refresh_token:
            return None

        try:
            return self.refresh()
        except Exception:
            return None

    def get_valid_token(self) -> str:
        """Return a valid access token, refreshing if necessary."""
        if not self.current_session:
            restored = self.restore_session()
            if not restored:
                env_token = os.getenv("MORPHY_ACCESS_TOKEN")
                if env_token:
                    return env_token
                raise AuthError("Authentication required. Please run /login.")

        if self.current_session.is_expired:
            self.refresh()

        return self.current_session.access_token

    def logout(self) -> None:
        """Sign out and invalidate session credentials."""
        if self.current_session and self.current_session.access_token and self.supabase_key:
            try:
                endpoint = f"{self.supabase_url}/auth/v1/logout"
                with httpx.Client(timeout=8.0) as client:
                    client.post(
                        endpoint,
                        headers={
                            "apikey": self.supabase_key,
                            "Authorization": f"Bearer {self.current_session.access_token}",
                        },
                    )
            except Exception:
                pass

        self._clear_stored_tokens()
        self.current_session = None

    def status(self) -> dict[str, Any]:
        """Return current status dictionary."""
        token = os.getenv("MORPHY_ACCESS_TOKEN")
        if token and not self.current_session:
            return {
                "authenticated": True,
                "source": "MORPHY_ACCESS_TOKEN environment variable",
                "email": "injected-environment-session",
                "supabase_url": self.supabase_url,
            }

        if not self.current_session:
            restored = self.restore_session()
            if not restored:
                return {
                    "authenticated": False,
                    "supabase_url": self.supabase_url,
                }

        remaining_sec = max(0, int(self.current_session.expires_at - time.time()))
        return {
            "authenticated": True,
            "email": self.current_session.email,
            "user_id": self.current_session.user_id,
            "expires_in_seconds": remaining_sec,
            "supabase_url": self.supabase_url,
        }

