"""Publish new durable audit events to a private Redis stream."""

import asyncio
import logging
import os

import asyncpg
from redis.asyncio import Redis
from redis.exceptions import RedisError


STREAM = "morphy:audit:v1"
BATCH_SIZE = 50
log = logging.getLogger("morphy.audit")


async def enable_outbox(conn):
    await conn.execute(
        "UPDATE morphy_private.audit_stream_settings SET enabled=true WHERE NOT enabled"
    )


async def publish_batch(conn, redis, stream=STREAM):
    async with conn.transaction():
        events = await conn.fetch("""
            SELECT a.id, a.org_id, a.action, a.occurred_at
            FROM morphy_private.audit_stream_outbox o
            JOIN public.audit_events a ON a.id=o.event_id
            ORDER BY o.event_id
            LIMIT $1 FOR UPDATE OF o SKIP LOCKED
        """, BATCH_SIZE)
        if not events:
            return 0
        async with redis.pipeline() as batch:
            for event in events:
                batch.xadd(
                    stream,
                    {
                        "event_id": str(event["id"]),
                        "org_id": str(event["org_id"]),
                        "action": event["action"],
                        "occurred_at": event["occurred_at"].isoformat(),
                    },
                    maxlen=10_000,
                    approximate=True,
                )
            await batch.execute()
        await conn.execute(
            "DELETE FROM morphy_private.audit_stream_outbox WHERE event_id=ANY($1::bigint[])",
            [event["id"] for event in events],
        )
        return len(events)


async def run(control_dsn, redis_url):
    async with Redis.from_url(
        redis_url, socket_timeout=2, socket_connect_timeout=1,
    ) as redis:
        while True:
            conn = None
            try:
                conn = await asyncpg.connect(control_dsn, timeout=8, command_timeout=8)
                await redis.ping()
                await enable_outbox(conn)
                while True:
                    if not await publish_batch(conn, redis):
                        await asyncio.sleep(1)
            except asyncpg.UndefinedTableError:
                raise SystemExit("Apply migration 007 before starting the audit worker.") from None
            except (asyncpg.PostgresError, RedisError, OSError, TimeoutError) as error:
                log.warning("Audit publishing will retry: %s", type(error).__name__)
            finally:
                if conn:
                    conn.terminate()
            await asyncio.sleep(3)


def main():
    control_dsn = os.getenv("MORPHY_CONTROL_DSN")
    redis_url = os.getenv("MORPHY_AUDIT_REDIS_URL")
    if not control_dsn or not redis_url:
        raise SystemExit("Configure MORPHY_CONTROL_DSN and MORPHY_AUDIT_REDIS_URL.")
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run(control_dsn, redis_url))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
