from __future__ import annotations

import json
import logging
import pickle
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from agent_core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    id: str
    channel: str
    chat_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source_type: str = "memory"  # memory, goal, trigger, summary, pattern

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "channel": self.channel,
            "chat_id": self.chat_id,
            "text": self.text,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "source_type": self.source_type,
        }
        if self.embedding is not None:
            d["embedding"] = self.embedding
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VectorDocument":
        return cls(**data)


class EmbeddingProvider:
    """Abstract embedding provider - can use local or API models."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dimension = 384  # MiniLM-L6-v2 dimension
        self._init_model()

    def _init_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info("Loaded embedding model: %s (dim=%d)", self.model_name, self._dimension)
        except ImportError:
            logger.warning("sentence-transformers not installed. Using random embeddings for development.")
            self._model = None

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return embeddings as (n, d) numpy array."""
        if self._model:
            return self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

        # Fallback: deterministic pseudo-random embeddings for dev
        np.random.seed(42)
        return np.random.randn(len(texts), self._dimension).astype(np.float32)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]

    @property
    def dimension(self) -> int:
        return self._dimension


class VectorIndex:
    """Simple in-memory vector index with persistence. For production, use FAISS, Chroma, or pgvector."""

    def __init__(self, index_dir: Path, provider: EmbeddingProvider):
        self.index_dir = index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.provider = provider
        self.dimension = provider.dimension

        # Storage
        self.vectors: dict[str, np.ndarray] = {}  # id -> embedding
        self.documents: dict[str, VectorDocument] = {}
        self._channel_index: dict[str, set[str]] = {}  # channel -> set of ids
        self._chat_index: dict[str, set[str]] = {}  # channel:chat_id -> set of ids

        self._load()

    def _get_index_path(self) -> Path:
        return self.index_dir / "vectors.pkl"

    def _get_meta_path(self) -> Path:
        return self.index_dir / "documents.json"

    def _load(self):
        try:
            # Load vectors
            vec_path = self._get_index_path()
            if vec_path.exists():
                with open(vec_path, "rb") as f:
                    self.vectors = pickle.load(f)

            # Load documents
            meta_path = self._get_meta_path()
            if meta_path.exists():
                data = json.loads(meta_path.read_text())
                for doc_data in data:
                    doc = VectorDocument.from_dict(doc_data)
                    self.documents[doc.id] = doc
                    # Rebuild indices
                    self._add_to_indices(doc)

            logger.info("Loaded vector index: %d vectors, %d documents", len(self.vectors), len(self.documents))
        except Exception as e:
            logger.warning("Failed to load vector index: %s", e)
            self.vectors = {}
            self.documents = {}

    def _save(self):
        try:
            # Save vectors
            with open(self._get_index_path(), "wb") as f:
                pickle.dump(self.vectors, f)

            # Save documents
            with open(self._get_meta_path(), "w") as f:
                json.dump([doc.to_dict() for doc in self.documents.values()], f, indent=2)
        except Exception as e:
            logger.error("Failed to save vector index: %s", e)

    def _add_to_indices(self, doc: VectorDocument):
        ch_key = doc.channel
        chat_key = f"{doc.channel}:{doc.chat_id}"

        if ch_key not in self._channel_index:
            self._channel_index[ch_key] = set()
        self._channel_index[ch_key].add(doc.id)

        if chat_key not in self._chat_index:
            self._chat_index[chat_key] = set()
        self._chat_index[chat_key].add(doc.id)

    def _remove_from_indices(self, doc: VectorDocument):
        ch_key = doc.channel
        chat_key = f"{doc.channel}:{doc.chat_id}"

        if ch_key in self._channel_index:
            self._channel_index[ch_key].discard(doc.id)
        if chat_key in self._chat_index:
            self._chat_index[chat_key].discard(doc.id)

    def add(self, doc: VectorDocument) -> str:
        """Add document to index, generate embedding if needed."""
        if doc.embedding is None:
            doc.embedding = self.provider.embed_one(doc.text).tolist()

        embedding = np.array(doc.embedding, dtype=np.float32)
        self.vectors[doc.id] = embedding
        self.documents[doc.id] = doc
        self._add_to_indices(doc)
        self._save()
        return doc.id

    def add_batch(self, docs: list[VectorDocument]) -> list[str]:
        """Add multiple documents efficiently."""
        texts = [d.text for d in docs]
        embeddings = self.provider.embed(texts)

        ids = []
        for doc, emb in zip(docs, embeddings):
            if doc.embedding is None:
                doc.embedding = emb.tolist()
            self.vectors[doc.id] = emb
            self.documents[doc.id] = doc
            self._add_to_indices(doc)
            ids.append(doc.id)

        self._save()
        return ids

    def remove(self, doc_id: str) -> bool:
        if doc_id in self.documents:
            doc = self.documents[doc_id]
            self._remove_from_indices(doc)
            del self.documents[doc_id]
            self.vectors.pop(doc_id, None)
            self._save()
            return True
        return False

    def search(
        self,
        query: str,
        channel: str | None = None,
        chat_id: str | None = None,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[VectorDocument, float]]:
        """Semantic search with optional channel/chat filtering."""
        if not self.vectors:
            return []

        # Get candidate IDs
        if chat_id:
            candidates = self._chat_index.get(f"{channel}:{chat_id}", set())
        elif channel:
            candidates = self._channel_index.get(channel, set())
        else:
            candidates = set(self.vectors.keys())

        if not candidates:
            return []

        # Filter vectors
        candidate_vecs = {k: self.vectors[k] for k in candidates if k in self.vectors}
        if not candidate_vecs:
            return []

        # Encode query
        query_emb = self.provider.embed_one(query)

        # Compute similarities (cosine since embeddings are normalized)
        results = []
        for doc_id, vec in candidate_vecs.items():
            score = float(np.dot(query_emb, vec))
            if score >= min_score:
                doc = self.documents.get(doc_id)
                if doc:
                    results.append((doc, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_vectors": len(self.vectors),
            "total_documents": len(self.documents),
            "dimension": self.dimension,
            "channels": len(self._channel_index),
            "chats": len(self._chat_index),
        }

    def rebuild_from_long_term_memory(self, channel: str, chat_id: str, limit: int = 1000) -> int:
        """Rebuild index from existing long-term memory."""
        from agent_core.memory import long_term_memory

        graph = long_term_memory.get_chat_graph(channel, chat_id, limit)
        nodes = graph.get("nodes", [])

        docs = []
        for node in nodes:
            doc = VectorDocument(
                id=f"ltm_{node['id']}",
                channel=channel,
                chat_id=chat_id,
                text=node.get("text", ""),
                metadata={
                    "ltm_id": node["id"],
                    "role": node.get("role"),
                    "source_message_id": node.get("source_message_id"),
                    "created_at": node.get("created_at"),
                },
                source_type="memory",
            )
            docs.append(doc)

        if docs:
            self.add_batch(docs)
        return len(docs)


# Global instances
_embedding_provider = EmbeddingProvider()
_vector_index = VectorIndex(
    Path(settings.resolved_agent_data_dir) / "vector_index",
    _embedding_provider,
)


def get_vector_index() -> VectorIndex:
    return _vector_index


def get_embedding_provider() -> EmbeddingProvider:
    return _embedding_provider


# Convenience functions
async def semantic_search(
    query: str,
    channel: str | None = None,
    chat_id: str | None = None,
    top_k: int = 10,
    min_score: float = 0.3,
) -> list[dict[str, Any]]:
    index = get_vector_index()
    results = index.search(query, channel, chat_id, top_k, min_score)
    return [
        {
            "document": doc.to_dict(),
            "score": score,
        }
        for doc, score in results
    ]


def index_document(
    channel: str,
    chat_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
    source_type: str = "memory",
    doc_id: str | None = None,
) -> str:
    import uuid
    index = get_vector_index()
    doc = VectorDocument(
        id=doc_id or uuid.uuid4().hex[:12],
        channel=channel,
        chat_id=chat_id,
        text=text,
        metadata=metadata or {},
        source_type=source_type,
    )
    index.add(doc)
    return doc.id
