"""Semantic retrieval for large permitted schemas with an offline fallback."""

import asyncio
from functools import lru_cache
import logging
import os
from . import vector_search

log = logging.getLogger("morphy")


@lru_cache(maxsize=1)
def local_encoder():
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            device="cpu",
            local_files_only=True,
            trust_remote_code=False,
        )
    except (ImportError, OSError, RuntimeError) as error:
        log.info("Offline vector retrieval unavailable: %s", type(error).__name__)
        return None


@lru_cache(maxsize=16)
def schema_vectors(descriptions):
    return local_encoder().encode(
        list(descriptions), normalize_embeddings=True, show_progress_bar=False
    )


def encode_context(question, tables):
    if len(tables) <= 12 or os.getenv("MORPHY_EMBEDDINGS", "auto") == "off":
        return None
    encoder = local_encoder()
    if encoder is None:
        return None
    names = sorted(tables)
    descriptions = tuple(
        (name + ": " + ", ".join(tables[name])).replace("_", " ")[:2000]
        for name in names
    )
    vector = encoder.encode(
        question, normalize_embeddings=True, show_progress_bar=False
    )
    return names, schema_vectors(descriptions), vector


async def semantic_anchors(question, tables, *, database_id=None):
    context = await asyncio.to_thread(encode_context, question, tables)
    if context is None:
        return []
    names, embeddings, vector = context
    if database_id is not None:
        anchors = await vector_search.search(database_id, tables, embeddings, vector)
        if anchors is not None:
            return anchors
    scores = embeddings @ vector
    return [
        names[i] for i in scores.argsort()[::-1][:vector_search.ANCHOR_LIMIT]
        if scores[i] >= vector_search.MIN_SIMILARITY
    ]
