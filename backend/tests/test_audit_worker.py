import asyncio
import os
import uuid
from unittest.mock import Mock

import asyncpg
import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.engine.audit_worker import enable_outbox, publish_batch


@pytest.mark.skipif(
    not os.getenv("MORPHY_INTEGRATION_DSN") or not os.getenv("MORPHY_TEST_REDIS_URL"),
    reason="Disposable PostgreSQL and Redis fixtures required",
)
def test_audit_outbox_survives_redis_failure_and_concurrent_workers():
    async def check():
        dsn = os.environ["MORPHY_INTEGRATION_DSN"]
        owner = uuid.uuid4()
        org = None
        stream = "morphy:test-audit:" + owner.hex
        first = await asyncpg.connect(dsn)
        second = await asyncpg.connect(dsn)
        async with Redis.from_url(os.environ["MORPHY_TEST_REDIS_URL"], decode_responses=True) as redis:
            try:
                async with first.transaction():
                    await first.execute("INSERT INTO auth.users(id) VALUES($1)", owner)
                    await first.execute(
                        "INSERT INTO public.profiles(id,username,display_name) VALUES($1,$2,'Audit fixture')",
                        owner, "audit_" + owner.hex[:12],
                    )
                    await first.execute("SELECT set_config('request.jwt.claim.sub',$1,true)", str(owner))
                    org = await first.fetchval("SELECT public.create_workspace('Audit fixture')")
                query = (
                    "INSERT INTO public.audit_events(org_id,actor_id,action) "
                    "VALUES($1,$2,'query.started') RETURNING id"
                )
                before = await first.fetchval(query, org, owner)
                assert not await first.fetchval(
                    "SELECT EXISTS(SELECT FROM morphy_private.audit_stream_outbox WHERE event_id=$1)", before,
                )
                assert not await first.fetchval(
                    "SELECT has_table_privilege('authenticated','morphy_private.audit_stream_outbox','SELECT')"
                )
                await enable_outbox(first)
                event = await first.fetchval(query, org, owner)
                broken = Mock()
                broken.pipeline.side_effect = RedisError("disposable failure")
                with pytest.raises(RedisError):
                    await publish_batch(first, broken, stream)
                assert await first.fetchval(
                    "SELECT event_id FROM morphy_private.audit_stream_outbox WHERE event_id=$1", event,
                ) == event
                counts = await asyncio.gather(
                    publish_batch(first, redis, stream), publish_batch(second, redis, stream),
                )
                assert sum(counts) == 1
                [(_, payload)] = await redis.xrange(stream)
                assert payload["event_id"] == str(event) and payload["org_id"] == str(org)
                assert set(payload) == {"event_id", "org_id", "occurred_at", "action"}
                assert await first.fetchval("SELECT action FROM public.audit_events WHERE id=$1", event) == "query.started"
                assert await publish_batch(first, redis, stream) == 0
            finally:
                await first.execute("UPDATE morphy_private.audit_stream_settings SET enabled=false")
                if org:
                    await first.execute("DELETE FROM public.organizations WHERE id=$1", org)
                await first.execute("DELETE FROM auth.users WHERE id=$1", owner)
                await redis.delete(stream)
                await first.close()
                await second.close()

    asyncio.run(check())
