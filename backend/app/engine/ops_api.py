"""Platform staff API. Customer roles and metadata never confer staff access."""

import base64
import binascii
import json
from typing import Annotated, Literal, NamedTuple
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .api import EngineRoute, control, identity, settings
from .ops_activity import enforce_access


router = APIRouter(prefix="/api/ops", tags=["Platform operations"], route_class=EngineRoute)
Kind = Literal["user", "organization", "source"]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100_000)]


class StaffSession(NamedTuple):
    conn: asyncpg.Connection
    actor: UUID
    role: str


def is_mfa_session(authorization, user):
    # Only called after identity() has had Supabase verify this same bearer token.
    try:
        _, payload, _ = authorization.removeprefix("Bearer ").split(".")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return (
            claims.get("aal") == "aal2" and claims.get("role") == "authenticated"
            and UUID(claims["sub"]) == user
        )
    except (AttributeError, KeyError, TypeError, ValueError, binascii.Error):
        return False


async def staff_session(
    response: Response, user=Depends(identity), config=Depends(settings),
    authorization: str = Header(default=""),
):
    response.headers["Cache-Control"] = "no-store"
    conn = await control(config)
    try:
        async with conn.transaction():
            role = await conn.fetchval(
                "SELECT role FROM morphy_private.ops_staff WHERE user_id=$1 FOR SHARE", user,
            )
            if role is None:
                raise HTTPException(403, "Platform staff access required.")
            if not is_mfa_session(authorization, user):
                raise HTTPException(403, {"code": "mfa_required", "message": "Complete MFA to use platform operations."})
            await enforce_access(conn, user)
            yield StaffSession(conn, user, role)
    finally:
        await conn.close()


Staff = Annotated[StaffSession, Depends(staff_session, scope="function")]


def require_role(staff, *roles):
    if staff.role not in roles:
        raise HTTPException(403, "This staff role cannot perform that action.")
    return staff.conn, staff.actor


@router.get("/me")
async def me(staff: Staff):
    return {"role": staff.role}


@router.get("/organizations")
async def organizations(
    staff: Staff, search: Annotated[str, Query(max_length=80)] = "",
    limit: Limit = 25, offset: Offset = 0,
):
    rows = await staff.conn.fetch("""
        WITH page AS (
          SELECT id,name,created_at FROM public.organizations
          WHERE strpos(lower(name),lower($1))>0 OR $1=''
          ORDER BY created_at DESC,id LIMIT $2 OFFSET $3
        )
        SELECT o.*, CASE WHEN morphy_private.active_control('organization',o.id)
                        THEN 'suspended' ELSE 'enabled' END AS account_status,
          (SELECT count(*) FROM public.memberships m WHERE m.org_id=o.id) AS members,
          greatest(o.created_at,
            (SELECT max(occurred_at) FROM public.audit_events a WHERE a.org_id=o.id),
            (SELECT max(started_at) FROM morphy_private.ops_jobs j WHERE j.org_id=o.id)
          ) AS last_activity,
          (SELECT count(DISTINCT activity.actor_id) FROM (
             SELECT actor_id FROM public.audit_events a WHERE a.org_id=o.id AND occurred_at>=now()-interval '7 days'
             UNION ALL
             SELECT actor_id FROM morphy_private.ops_jobs j WHERE j.org_id=o.id AND started_at>=now()-interval '7 days'
           ) activity JOIN public.memberships m ON m.org_id=o.id AND m.user_id=activity.actor_id) AS active_members_7d,
          (SELECT count(*) FROM morphy_private.ops_jobs j WHERE j.org_id=o.id
           AND j.state='running' AND started_at>=now()-interval '10 minutes') AS running_jobs
        FROM page o ORDER BY o.created_at DESC,o.id
    """, search.strip(), limit, offset)
    return {"items": [dict(row) for row in rows]}


@router.get("/organizations/{org_id}/members")
async def members(org_id: UUID, staff: Staff, limit: Limit = 25, offset: Offset = 0):
    rows = await staff.conn.fetch("""
        SELECT p.id,p.username,r.name AS role,
          CASE WHEN morphy_private.active_control('user',p.id) THEN 'suspended' ELSE 'enabled' END AS account_status
        FROM public.memberships m JOIN public.profiles p ON p.id=m.user_id
        JOIN public.roles r ON r.id=m.role_id WHERE m.org_id=$1
        ORDER BY p.username,p.id LIMIT $2 OFFSET $3
    """, org_id, limit, offset)
    return {"items": [dict(row) for row in rows]}


@router.get("/organizations/{org_id}/sources")
async def sources(org_id: UUID, staff: Staff, limit: Limit = 25, offset: Offset = 0):
    rows = await staff.conn.fetch("""
        SELECT id,dialect,morphy_private.active_control('source',id) AS quarantined
        FROM public.target_databases WHERE org_id=$1 ORDER BY id LIMIT $2 OFFSET $3
    """, org_id, limit, offset)
    return {"items": [dict(row) for row in rows]}


@router.get("/jobs")
async def jobs(staff: Staff, org_id: UUID | None = None, attention: bool = False,
               limit: Limit = 25, offset: Offset = 0):
    rows = await staff.conn.fetch("""
        SELECT id,org_id,actor_id,source_id,kind,model_used,prompt_flagged,code,started_at,finished_at,
          CASE WHEN state='running' AND started_at<now()-interval '10 minutes'
            THEN 'unknown' ELSE state END AS state
        FROM morphy_private.ops_jobs WHERE started_at>=now()-interval '30 days'
          AND ($1::uuid IS NULL OR org_id=$1)
          AND (NOT $2 OR state IN ('failed','rejected') OR prompt_flagged
            OR (state='running' AND started_at<now()-interval '10 minutes'))
        ORDER BY started_at DESC,id LIMIT $3 OFFSET $4
    """, org_id, attention, limit, offset)
    return {"items": [dict(row) for row in rows]}


@router.get("/signals")
async def signals(staff: Staff, org_id: UUID | None = None, limit: Limit = 25, offset: Offset = 0):
    rows = await staff.conn.fetch("""
        WITH counts AS (
          SELECT org_id,actor_id,source_id,max(started_at) AS last_activity,
             count(*) FILTER (WHERE code='policy_denied' AND kind='query') AS blocked,
             count(*) FILTER (WHERE model_used) AS model_generations,
             count(*) FILTER (WHERE code='file_type_mismatch') AS mismatches,
             count(*) FILTER (WHERE prompt_flagged) AS overrides
          FROM morphy_private.ops_jobs WHERE started_at>=now()-interval '15 minutes'
            AND ($1::uuid IS NULL OR org_id=$1) GROUP BY org_id,actor_id,source_id
        ) SELECT c.org_id,c.actor_id,c.source_id,c.last_activity,s.code,s.occurrences
          FROM counts c CROSS JOIN LATERAL (VALUES
            ('repeated_blocked_queries',c.blocked,5),('model_usage_burst',c.model_generations,20),
            ('file_type_mismatch',c.mismatches,1),('possible_prompt_override',c.overrides,1)
          ) s(code,occurrences,threshold) WHERE s.occurrences>=s.threshold
          ORDER BY last_activity DESC,org_id,actor_id,source_id,s.code LIMIT $2 OFFSET $3
    """, org_id, limit, offset)
    return {"items": [dict(row) for row in rows]}


async def require_target(conn, kind, target_id, *, lock=False):
    table = {"user": "auth.users", "organization": "public.organizations", "source": "public.target_databases"}[kind]
    clause = " FOR UPDATE" if lock else ""
    if not await conn.fetchval(f"SELECT true FROM {table} WHERE id=$1{clause}", target_id):
        raise HTTPException(404, "Target unavailable.")


class IncidentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    target_id: UUID
    reason: Reason
    job_id: UUID | None = None


class ResolutionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reason


class RestrictionInput(ResolutionInput):
    duration_minutes: int | None = Field(default=None, ge=1, le=43200, strict=True)


@router.get("/incidents")
async def incidents(staff: Staff, state: Literal["open", "closed", "all"] = "open",
                    limit: Limit = 25, offset: Offset = 0):
    rows = await staff.conn.fetch("""
        SELECT * FROM morphy_private.ops_incidents
        WHERE $1='all' OR (closed_at IS NULL)=($1='open')
        ORDER BY opened_at DESC,id LIMIT $2 OFFSET $3
    """, state, limit, offset)
    return {"items": [dict(row) for row in rows]}


@router.post("/incidents", status_code=201)
async def open_incident(payload: IncidentInput, staff: Staff):
    conn, actor = require_role(staff, "reviewer", "operator")
    await require_target(conn, payload.kind, payload.target_id)
    if payload.job_id:
        field = {"user": "actor_id", "organization": "org_id", "source": "source_id"}[payload.kind]
        if not await conn.fetchval(
            f"SELECT 1 FROM morphy_private.ops_jobs WHERE id=$1 AND {field}=$2", payload.job_id, payload.target_id,
        ):
            raise HTTPException(422, "The job does not match the incident target.")
    row = await conn.fetchrow("""
        INSERT INTO morphy_private.ops_incidents(kind,target_id,reason,job_id,opened_by)
        VALUES($1,$2,$3,$4,$5) RETURNING *
    """, payload.kind, payload.target_id, payload.reason, payload.job_id, actor)
    return dict(row)


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(incident_id: UUID, payload: ResolutionInput, staff: Staff):
    conn, actor = require_role(staff, "reviewer", "operator")
    row = await conn.fetchrow("""
        UPDATE morphy_private.ops_incidents SET closed_by=$2,closed_at=now(),resolution=$3
        WHERE id=$1 AND closed_at IS NULL RETURNING *
    """, incident_id, actor, payload.reason)
    if row is None:
        raise HTTPException(409, "The incident is closed or unavailable.")
    return dict(row)


@router.get("/controls/{kind}/{target_id}")
async def control_status(kind: Kind, target_id: UUID, staff: Staff, limit: Limit = 25, offset: Offset = 0):
    conn = staff.conn
    active = await conn.fetchrow("""
        SELECT expires_at FROM morphy_private.ops_controls
        WHERE kind=$1 AND target_id=$2 AND (expires_at IS NULL OR expires_at>now())
    """, kind, target_id)
    actions = await conn.fetch("""
        SELECT id,actor_id,action,reason,expires_at,occurred_at FROM morphy_private.ops_actions
        WHERE kind=$1 AND target_id=$2 ORDER BY id DESC LIMIT $3 OFFSET $4
    """, kind, target_id, limit, offset)
    return {"restriction": dict(active) if active else None, "items": [dict(row) for row in actions]}


@router.put("/controls/{kind}/{target_id}")
async def restrict_target(kind: Kind, target_id: UUID, payload: RestrictionInput, staff: Staff):
    conn, actor = require_role(staff, "operator")
    if (payload.duration_minutes is None) != (kind == "source"):
        raise HTTPException(422, "Specify a duration for account suspensions only.")
    await require_target(conn, kind, target_id, lock=True)
    if kind == "user" and await conn.fetchval(
        "SELECT 1 FROM morphy_private.ops_staff WHERE user_id=$1", target_id,
    ):
        raise HTTPException(409, "Revoke staff access before suspending this account.")
    row = await conn.fetchrow("""
        INSERT INTO morphy_private.ops_controls(kind,target_id,expires_at)
        VALUES($1,$2,now()+make_interval(mins=>$3::int))
        ON CONFLICT(kind,target_id) DO UPDATE SET expires_at=excluded.expires_at
        WHERE morphy_private.ops_controls.expires_at<=now() RETURNING expires_at
    """, kind, target_id, payload.duration_minutes)
    if row is None:
        raise HTTPException(409, "This target already has an active restriction.")
    await record_action(conn, actor, kind, target_id, "restrict", payload.reason, row["expires_at"])
    return dict(row)


@router.post("/controls/{kind}/{target_id}/restore")
async def restore_target(kind: Kind, target_id: UUID, payload: ResolutionInput, staff: Staff):
    conn, actor = require_role(staff, "operator")
    result = await conn.fetchval("""
        DELETE FROM morphy_private.ops_controls WHERE kind=$1 AND target_id=$2
          AND (expires_at IS NULL OR expires_at>now()) RETURNING true
    """, kind, target_id)
    if not result:
        raise HTTPException(409, "There is no active restriction to restore.")
    await record_action(conn, actor, kind, target_id, "restore", payload.reason, None)
    return {"restored": True}


async def record_action(conn, actor, kind, target_id, action, reason, expires_at):
    await conn.execute("""
        INSERT INTO morphy_private.ops_actions(actor_id,kind,target_id,action,reason,expires_at)
        VALUES($1,$2,$3,$4,$5,$6)
    """, actor, kind, target_id, action, reason, expires_at)
