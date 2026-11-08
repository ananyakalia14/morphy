import asyncio
import os
import uuid
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis

from app.engine import retrieval, vector_search


def unit_vector(position):
    return tuple(float(i == position) for i in range(vector_search.DIMENSIONS))


def test_schema_fingerprint_scopes_by_source_column_and_type():
    first = {"orders": {"amount": "int", "private_note": "text"}}
    second = {"orders": {"amount": "int"}}
    first_key = vector_search.fingerprint("db1", first)
    assert first_key != vector_search.fingerprint("db2", first)
    assert first_key != vector_search.fingerprint("db1", second)
    assert first_key != vector_search.fingerprint("db1", {"orders": {"amount": "text"}})


def test_offline_anchors_survive_redis_unavailability(monkeypatch):
    class Embeddings:
        def __matmul__(self, vector):
            return Scores([0.1, 0.9, 0.3])

    class Scores(list):
        def argsort(self):
            return sorted(range(len(self)), key=self.__getitem__)

    tables = {"a": {"id": "int"}, "b": {"id": "int"}, "c": {"id": "int"}}
    monkeypatch.setattr(
        retrieval, "encode_context",
        lambda question, schema: (sorted(schema), Embeddings(), unit_vector(1)),
    )
    remote = AsyncMock(return_value=None)
    monkeypatch.setattr(vector_search, "search", remote)
    assert asyncio.run(retrieval.semantic_anchors("test question", tables, database_id="db")) == ["b", "c"]
    assert remote.await_args.args[:2] == ("db", tables)


@pytest.mark.skipif(not os.getenv("MORPHY_TEST_SEARCH_URL"), reason="Redis Search fixture required")
def test_redis_hnsw_filters_by_permitted_schema(monkeypatch):
    url = os.environ["MORPHY_TEST_SEARCH_URL"]
    monkeypatch.setenv("MORPHY_REDIS_URL", url)
    monkeypatch.setenv("MORPHY_REDIS_SEMANTIC", "1")
    source = uuid.uuid4()
    other_source = uuid.uuid4()
    restricted = {"orders": {"amount": "int"}, "products": {"id": "int"}}
    expanded = {**restricted, "staff_private": {"salary": "int"}}

    async def check():
        async with Redis.from_url(url, decode_responses=True) as redis:
            scopes = [(source, restricted), (source, expanded), (other_source, restricted)]
            try:
                a, b = unit_vector(1), unit_vector(2)
                assert await vector_search.search(source, expanded, [a, a, b], b) == ["staff_private"]
                assert await vector_search.search(source, restricted, [b, a], b) == ["orders"]
                assert await vector_search.search(other_source, restricted, [a, b], b) == ["products"]
                scope = vector_search.fingerprint(source, restricted)
                key = vector_search.PREFIX + scope + ":0"
                assert set(await redis.hkeys(key)) == {"scope", "embedding"}
                assert 3500 <= await redis.ttl(key) <= 3600
                await redis.delete(key)
                assert await vector_search.search(source, restricted, [b, a], b) is None
            finally:
                for db, tables in scopes:
                    scope = vector_search.fingerprint(db, tables)
                    await redis.delete(
                        "morphy:schema-ready:v1:" + scope,
                        *(vector_search.PREFIX + scope + ":" + str(i) for i in range(len(tables))),
                    )

    asyncio.run(check())
