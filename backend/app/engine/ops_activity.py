"""Record bounded operational metadata for authorized work."""

import asyncio
import logging
import os
import re
import socket
import time
from contextlib import asynccontextmanager, suppress

import asyncpg
from fastapi import HTTPException
from starlette.requests import ClientDisconnect


log = logging.getLogger(__name__)
OUTCOMES = {
    "query": {403: "policy_denied", 413: "result_limit", 422: "invalid_query"},
    "import": {403: "policy_denied", 413: "file_limit", 422: "invalid_file", 503: "import_unavailable"},
    "generation": {422: "generation_rejected", 503: "model_unavailable"},
}
PROMPT_OVERRIDE = re.compile(
    r"\b(?:ignore|disregard|override)\b.{0,40}\b(?:previous|prior|system|developer)\b.{0,30}\binstructions?\b"
    r"|\b(?:reveal|print|show|repeat)\b.{0,30}\b(?:system|developer) prompt\b",
    re.IGNORECASE | re.DOTALL,
)


class FileTypeMismatch(HTTPException):
    def __init__(self):
        super().__init__(422, "The upload does not match its declared file format.")


def publish_metrics(kind, state, code, elapsed_ms):
    """Send an allowlisted payload to an opt-in, local DogStatsD agent."""
    port = os.getenv("MORPHY_DOGSTATSD_PORT")
    if not port or kind not in OUTCOMES:
        return
    if state not in {"succeeded", "rejected", "failed", "cancelled"}:
        return
    if code is not None and code not in {
        *OUTCOMES[kind].values(), "file_type_mismatch", "service_error", "interrupted",
    }:
        return
    tags = f"kind:{kind},state:{state},code:{code or 'none'}"
    packet = f"morphy.ops.jobs:1|c|#{tags}\nmorphy.ops.duration_ms:{elapsed_ms:.1f}|d|#{tags}"
    with suppress(OSError, ValueError, OverflowError):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as agent:
            agent.setblocking(False)
            agent.sendto(packet.encode("ascii"), ("127.0.0.1", int(port)))


async def enforce_access(conn, user, org=None, source=None):
    block = await conn.fetchval(
        "SELECT morphy_private.access_block($1,$2,$3)", user, org, source,
    )
    if block:
        raise HTTPException(403, {
            "user_suspended": "This MORPHY account is suspended.",
            "organization_suspended": "This organization is suspended.",
            "source_quarantined": "This source is quarantined.",
        }[block])


@asynccontextmanager
async def track_operation(open_control, *, org, actor, source, kind, prompt_flagged=False):
    conn = await open_control()
    try:
        job_id = await conn.fetchval(
            """INSERT INTO morphy_private.ops_jobs(org_id,actor_id,source_id,kind,prompt_flagged)
               VALUES($1,$2,$3,$4,$5) RETURNING id""",
            org, actor, source, kind, prompt_flagged,
        )
    finally:
        await conn.close()

    started = time.monotonic()
    state, code = "succeeded", None
    model_used = False

    def use_model():
        nonlocal model_used
        model_used = True

    try:
        yield use_model
    except (asyncio.CancelledError, ClientDisconnect):
        state, code = "cancelled", "interrupted"
        raise
    except FileTypeMismatch:
        state, code = "rejected", "file_type_mismatch"
        raise
    except HTTPException as error:
        state = "rejected" if error.status_code < 500 else "failed"
        code = OUTCOMES[kind].get(error.status_code, "service_error")
        if code == "model_unavailable" and not model_used:
            code = "service_error"
        raise
    except Exception:
        state, code = "failed", "service_error"
        raise
    finally:
        try:
            conn = await open_control()
            try:
                await conn.execute(
                    """UPDATE morphy_private.ops_jobs SET state=$2,code=$3,
                       model_used=$4,finished_at=clock_timestamp() WHERE id=$1""",
                    job_id, state, code, model_used,
                )
            finally:
                await conn.close()
        except (asyncpg.PostgresError, OSError, TimeoutError):
            log.warning("Could not finish an operations event")
        publish_metrics(kind, state, code, (time.monotonic() - started) * 1000)
