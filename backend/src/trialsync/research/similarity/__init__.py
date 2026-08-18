"""Exact FAISS cosine-similarity index for frozen R6 representations."""

from .index import (
    ExactSimilarityIndex,
    IndexMetadataMismatchError,
    SimilarityIndexMetadata,
    build_exact_faiss_index,
    query_neighbors,
    verify_exact_neighbors,
)

__all__ = [
    "ExactSimilarityIndex",
    "IndexMetadataMismatchError",
    "SimilarityIndexMetadata",
    "build_exact_faiss_index",
    "query_neighbors",
    "verify_exact_neighbors",
]
