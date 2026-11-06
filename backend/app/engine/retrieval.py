"""Optional offline vector retrieval for large permitted schemas."""

from functools import lru_cache
import logging
import os

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


def semantic_anchors(question, tables):
    if len(tables) <= 12 or os.getenv("MORPHY_EMBEDDINGS", "auto") == "off":
        return []
    encoder = local_encoder()
    if encoder is None:
        return []
    names = sorted(tables)
    descriptions = tuple(
        (name + ": " + ", ".join(tables[name])).replace("_", " ")[:2000]
        for name in names
    )
    vector = encoder.encode(
        question, normalize_embeddings=True, show_progress_bar=False
    )
    scores = schema_vectors(descriptions) @ vector
    return [names[i] for i in scores.argsort()[::-1][:5] if scores[i] >= 0.20]
