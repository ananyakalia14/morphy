"""Client for Supabase control-plane RPCs and PostgREST tables."""

from typing import Any, Optional
import uuid
import httpx

from .auth import AuthManager, AuthError


class ControlPlaneError(Exception):
    """Error during control plane operations."""
    pass


class ControlClient:
    """Interacts with Supabase PostgREST endpoints and RPCs."""

    def __init__(self, auth_manager: AuthManager):
        self.auth = auth_manager

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[Any] = None,
    ) -> Any:
        token = self.auth.get_valid_token()
        headers = {
            "apikey": self.auth.supabase_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        url = f"{self.auth.supabase_url}{path}"

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.request(method, url, headers=headers, params=params, json=json_body)
        except httpx.HTTPError as exc:
            raise ControlPlaneError(f"Network error accessing control plane: {exc}")

        if resp.is_error:
            try:
                err = resp.json()
                detail = err.get("message") or err.get("detail") or resp.text
            except Exception:
                detail = resp.text
            raise ControlPlaneError(f"Control plane error ({resp.status_code}): {detail}")

        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # --- Profile ---

    def get_profile(self) -> Optional[dict[str, Any]]:
        status = self.auth.status()
        user_id = status.get("user_id")
        if not user_id:
            res = self._request("GET", "/rest/v1/profiles?select=*")
            return res[0] if res else None

        res = self._request("GET", f"/rest/v1/profiles?id=eq.{user_id}&select=*")
        return res[0] if res else None

    def claim_profile(self, username: str, display_name: str) -> None:
        self._request(
            "POST",
            "/rest/v1/rpc/claim_profile",
            json_body={"handle": username.strip().lower(), "full_name": display_name.strip()},
        )

    def update_profile(self, display_name: str, avatar_path: Optional[str] = None) -> None:
        try:
            self._request(
                "POST",
                "/rest/v1/rpc/update_profile",
                json_body={"full_name": display_name.strip(), "avatar": avatar_path},
            )
            return
        except Exception:
            pass

        profile = self.get_profile()
        user_id = profile.get("id") if profile else None
        if not user_id:
            status = self.auth.status()
            user_id = status.get("user_id")
        if not user_id:
            raise ControlPlaneError("Must be authenticated with a claimed profile to edit.")
        self._request(
            "PATCH",
            f"/rest/v1/profiles?id=eq.{user_id}",
            json_body={"display_name": display_name.strip()},
        )

    # --- Organizations ---

    def list_organizations(self) -> list[dict[str, Any]]:
        return self._request("GET", "/rest/v1/organizations?select=*&order=name.asc") or []

    def create_organization(self, name: str) -> str:
        res = self._request(
            "POST",
            "/rest/v1/rpc/create_workspace",
            json_body={"title": name.strip()},
        )
        return str(res)

    # --- Target Databases ---

    def list_databases(self, org_id: Optional[str] = None) -> list[dict[str, Any]]:
        query = "/rest/v1/target_databases?select=*&order=name.asc"
        if org_id:
            query += f"&org_id=eq.{org_id}"
        return self._request("GET", query) or []

    def register_database(self, org_id: str, name: str, dialect: str) -> str:
        res = self._request(
            "POST",
            "/rest/v1/rpc/register_database",
            json_body={"o": org_id, "title": name.strip(), "engine": dialect.strip().lower()},
        )
        return str(res)

    # --- Members & Roles ---

    def list_roles(self, org_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/rest/v1/roles?org_id=eq.{org_id}&select=*") or []

    def list_members(self, org_id: str) -> list[dict[str, Any]]:
        return self._request(
            "POST",
            "/rest/v1/rpc/org_people",
            json_body={"o": org_id},
        ) or []

    def set_member_role(self, org_id: str, user_id: str, role_id: str) -> None:
        self._request(
            "POST",
            "/rest/v1/rpc/set_member_role",
            json_body={"o": org_id, "person": user_id, "r": role_id},
        )

    # --- Invitations ---

    def list_invitations(self) -> list[dict[str, Any]]:
        return self._request("GET", "/rest/v1/invitations?select=*&order=created_at.desc") or []

    def invite_person(self, org_id: str, user_id: str, role_id: str) -> None:
        self._request(
            "POST",
            "/rest/v1/rpc/invite_person",
            json_body={"o": org_id, "person": user_id, "r": role_id},
        )

    def accept_invitation(self, invitation_id: str) -> None:
        self._request(
            "POST",
            "/rest/v1/rpc/accept_invitation",
            json_body={"inv": invitation_id},
        )

    def withdraw_invitation(self, invitation_id: str) -> None:
        try:
            self._request(
                "POST",
                "/rest/v1/rpc/revoke_invitation",
                json_body={"inv": invitation_id},
            )
            return
        except Exception:
            pass

        self._request(
            "DELETE",
            f"/rest/v1/invitations?id=eq.{invitation_id}",
        )

    def find_people(self, prefix: str) -> list[dict[str, Any]]:
        return self._request(
            "POST",
            "/rest/v1/rpc/find_people",
            json_body={"prefix": prefix.strip().lower()},
        ) or []

    # --- Dashboards & Panels (004) ---

    def list_dashboards(
        self, org_id: Optional[str] = None, database_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        query = "/rest/v1/dashboards?select=*,dashboard_panels(*)&order=updated_at.desc"
        if org_id:
            query += f"&org_id=eq.{org_id}"
        if database_id:
            query += f"&database_id=eq.{database_id}"
        return self._request("GET", query) or []

    def get_dashboard(self, dashboard_id: str) -> Optional[dict[str, Any]]:
        res = self._request(
            "GET",
            f"/rest/v1/dashboards?id=eq.{dashboard_id}&select=*,dashboard_panels(*)",
        )
        return res[0] if res else None

    def create_dashboard(
        self, org_id: str, database_id: str, title: str, shared: bool = False
    ) -> str:
        res = self._request(
            "POST",
            "/rest/v1/dashboards",
            json_body={
                "org_id": org_id,
                "database_id": database_id,
                "title": title.strip(),
                "shared": shared,
            },
        )
        if isinstance(res, list) and res:
            return str(res[0].get("id"))
        return str(res)

    def add_dashboard_panel(
        self, dashboard_id: str, database_id: str, query_id: str, position: int = 0
    ) -> None:
        self._request(
            "POST",
            "/rest/v1/dashboard_panels",
            json_body={
                "dashboard_id": dashboard_id,
                "database_id": database_id,
                "query_id": query_id,
                "position": position,
            },
        )

    def delete_dashboard(self, dashboard_id: str) -> None:
        self._request("DELETE", f"/rest/v1/dashboards?id=eq.{dashboard_id}")

    # --- Cloud Saved Queries (003) ---

    def list_saved_queries(
        self, org_id: Optional[str] = None, database_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        query = "/rest/v1/saved_queries?select=*&order=updated_at.desc"
        if org_id:
            query += f"&org_id=eq.{org_id}"
        if database_id:
            query += f"&database_id=eq.{database_id}"
        return self._request("GET", query) or []

    def create_saved_query(
        self, org_id: str, database_id: str, title: str, sql_text: str, shared: bool = False
    ) -> str:
        res = self._request(
            "POST",
            "/rest/v1/saved_queries",
            json_body={
                "org_id": org_id,
                "database_id": database_id,
                "title": title.strip(),
                "sql_text": sql_text.strip(),
                "shared": shared,
            },
        )
        if isinstance(res, list) and res:
            return str(res[0].get("id"))
        return str(res)

    def delete_saved_query(self, query_id: str) -> None:
        self._request("DELETE", f"/rest/v1/saved_queries?id=eq.{query_id}")

    # --- Permissions & Access Policy ---

    def save_permission(
        self,
        org_id: str,
        database_id: str,
        role_id: Optional[str] = None,
        user_id: Optional[str] = None,
        level: str = "QUERY_ONLY",
        cols: Optional[dict[str, list[str]]] = None,
        rules: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        self._request(
            "POST",
            "/rest/v1/rpc/save_permission",
            json_body={
                "o": org_id,
                "d": database_id,
                "r": role_id,
                "person": user_id,
                "level": level,
                "cols": cols or {},
                "rules": rules or [],
            },
        )

    def revoke_permission(
        self,
        org_id: str,
        database_id: str,
        role_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        self.save_permission(
            org_id=org_id,
            database_id=database_id,
            role_id=role_id,
            user_id=user_id,
            level="NONE",
            cols={},
            rules=[],
        )

    def effective_permission(self, database_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/rest/v1/rpc/effective_permission",
            json_body={"d": database_id},
        ) or {"mode": "NONE", "table_columns": {}, "row_rules": []}

