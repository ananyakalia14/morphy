"""Optional Redis HNSW search for permission-scoped schema embeddings."""

import asyncio
import hashlib
import json
import os
import struct

from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError


INDEX = "morphy:schema-index:v1"
PREFIX = "morphy:schema-vector:v1:"
DIMENSIONS = 384
TTL_SECONDS = 3600
ANCHOR_LIMIT = 5
MIN_SIMILARITY = 0.20


def fingerprint(database_id, tables):
    payload = json.dumps(
        ["all-MiniLM-L6-v2", str(database_id), tables],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def packed(vector):
    return struct.pack(f"<{DIMENSIONS}f", *vector)


async def create_index(client):
    try:
        await client.execute_command(
            "FT.CREATE", INDEX, "ON", "HASH", "PREFIX", 1, PREFIX, "SCHEMA",
            "scope", "TAG", "embedding", "VECTOR", "HNSW", 6,
            "TYPE", "FLOAT32", "DIM", DIMENSIONS, "DISTANCE_METRIC", "COSINE",
        )
    except ResponseError as error:
        if "index already exists" not in str(error).lower():
            raise


async def search(database_id, tables, embeddings, question_embedding):
    url = os.getenv("MORPHY_REDIS_URL")
    if not url or os.getenv("MORPHY_REDIS_SEMANTIC") != "1" or len(tables) > 128:
        return None

    names = sorted(tables)
    scope = fingerprint(database_id, tables)
    key_prefix = PREFIX + scope + ":"
    ready = "morphy:schema-ready:v1:" + scope
    count = min(ANCHOR_LIMIT, len(names))
    try:
        async with asyncio.timeout(2), Redis.from_url(
            url, protocol=2, decode_responses=True,
            socket_timeout=1, socket_connect_timeout=0.5,
        ) as client:
            if not await client.exists(ready):
                await create_index(client)
                async with client.pipeline() as batch:
                    for index, embedding in enumerate(embeddings):
                        key = key_prefix + str(index)
                        batch.hset(key, mapping={"scope": scope, "embedding": packed(embedding)})
                        batch.expire(key, TTL_SECONDS)
                    batch.set(ready, "1", ex=TTL_SECONDS)
                    await batch.execute()
            reply = await client.execute_command(
                "FT.SEARCH", INDEX, f"@scope:{{{scope}}}=>[KNN {count} @embedding $vector AS distance]",
                "PARAMS", 2, "vector", packed(question_embedding),
                "SORTBY", "distance", "ASC", "RETURN", 1, "distance",
                "LIMIT", 0, count, "DIALECT", 2,
            )
        if not isinstance(reply, list) or len(reply) != 1 + count * 2:
            return None
        result = []
        for key, fields in zip(reply[1::2], reply[2::2]):
            if not isinstance(key, str) or not key.startswith(key_prefix) or fields[0] != "distance":
                return None
            index = int(key[len(key_prefix):])
            if not 0 <= index < len(names):
                return None
            if float(fields[1]) <= 1 - MIN_SIMILARITY:
                result.append(names[index])
        return result
    except (RedisError, TimeoutError, ValueError, TypeError, IndexError, struct.error):
        return None
