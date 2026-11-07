import asyncio
import os
import uuid

import pytest
from redis.asyncio import Redis
from app.engine.cache import read_draft, store_draft
from app.engine.cache import generation_key


def test_generation_cache_is_scoped_to_database_policy_and_schema():
    args = ["db-a","total","model",{"orders":{"id":"int"}},{"mode":"QUERY_ONLY"},[]]
    key = generation_key(*args)
    for index, value in [(0,"db-b"),(1,"other question"),(2,"other model"),
                         (3,{"orders":{"id":"text"}}),(4,{"mode":"NONE"}),
                         (5,[("a","id","b","id")])]:
        changed = args.copy()
        changed[index] = value
        assert generation_key(*changed) != key


@pytest.mark.skipif(not os.getenv("MORPHY_TEST_REDIS_URL"), reason="Disposable Redis required")
def test_redis_draft_round_trip(monkeypatch):
    url = os.environ["MORPHY_TEST_REDIS_URL"]
    monkeypatch.setenv("MORPHY_REDIS_URL", url)
    db = uuid.uuid4()
    schema = {"orders": {"amount": "int"}}
    policy = {"mode": "QUERY_ONLY", "table_columns": {"orders": ["amount"]}}
    key = generation_key(db, "total", "model", schema, policy, [])
    revoked = generation_key(db, "total", "model", schema, {"mode": "NONE"}, [])

    async def check():
        async with Redis.from_url(url) as client:
            try:
                assert await read_draft(key) is None
                await store_draft(key, "SELECT SUM(amount) FROM orders")
                assert await read_draft(key) == "SELECT SUM(amount) FROM orders"
                assert await read_draft(revoked) is None
                assert 86300 <= await client.ttl(key) <= 86400
            finally:
                await client.delete(key)

    asyncio.run(check())
