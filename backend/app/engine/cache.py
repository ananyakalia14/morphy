"""Optional Redis storage for generated SQL. Result rows never enter the cache."""

import hashlib
import json
import os
from contextlib import asynccontextmanager
from redis.asyncio import Redis
from redis.exceptions import RedisError


def generation_key(database, question, model, schema, policy, edges):
    payload = [
        "v2",
        str(database),
        question,
        model,
        schema,
        policy,
        sorted(tuple(e) for e in edges),
    ]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return "morphy:draft:" + digest


@asynccontextmanager
async def cache_client():
    url = os.getenv("MORPHY_REDIS_URL")
    if not url:
        yield None
        return
    client = Redis.from_url(
        url, socket_timeout=1, socket_connect_timeout=0.5, decode_responses=True
    )
    try:
        yield client
    finally:
        await client.aclose()


async def read_draft(key):
    try:
        async with cache_client() as client:
            return await client.get(key) if client else None
    except RedisError:
        return None


async def store_draft(key, sql):
    try:
        async with cache_client() as client:
            if client:
                await client.set(key, sql, ex=86400)
    except RedisError:
        pass
