"""Corpus retrieval. FAISS is used when an index exists; otherwise token overlap."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

TOKEN = re.compile(r"[a-z0-9]+")


def chunk_corpus(corpus_dir: Path) -> list[dict]:
    passages = []
    for path in sorted(corpus_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = path.stem
        blocks = re.split(r"\n(?=#)", text)
        for index, block in enumerate(blocks):
            cleaned = block.strip()
            if not cleaned:
                continue
            heading = next((line[2:].strip() for line in cleaned.splitlines() if line.startswith("# ")), title)
            passages.append(
                {
                    "source_id": f"{path.relative_to(corpus_dir).as_posix()}#{index}",
                    "title": heading,
                    "text": cleaned,
                }
            )
    return passages


def _tokens(text: str) -> set[str]:
    return set(TOKEN.findall(text.lower()))


def overlap_search(passages: list[dict], question: str, limit: int = 3) -> list[dict]:
    query = _tokens(question)
    if not query:
        return []
    scored = []
    for passage in passages:
        tokens = _tokens(passage["title"] + " " + passage["text"])
        score = len(query & tokens) / len(query)
        if score > 0:
            scored.append((score, passage))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [passage for _score, passage in scored[:limit]]


class Retriever:
    def __init__(self, corpus_dir: Path, cache_dir: Path):
        self.corpus_dir = corpus_dir
        self.cache_dir = cache_dir
        self.chunk_path = cache_dir / "corpus_chunks.json"
        self.index_path = cache_dir / "corpus.faiss"
        self.matrix_path = cache_dir / "corpus_vectors.npy"

    def passages(self) -> list[dict]:
        if self.chunk_path.is_file():
            return json.loads(self.chunk_path.read_text(encoding="utf-8"))
        return chunk_corpus(self.corpus_dir)

    def build_index(self) -> int:
        passages = chunk_corpus(self.corpus_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_path.write_text(json.dumps(passages), encoding="utf-8")
        vectors = _embed([passage["text"] for passage in passages])
        if vectors is None:
            return len(passages)
        self._write_index(vectors)
        return len(passages)

    def search(self, question: str, limit: int = 3) -> list[dict]:
        passages = self.passages()
        if not passages:
            return []
        vectors = self._load_vectors()
        if vectors is not None:
            query = _embed([question])
            if query is not None:
                return _vector_search(passages, vectors, query[0], limit)
        return overlap_search(passages, question, limit)

    def _write_index(self, vectors) -> None:
        import numpy as np

        np.save(self.matrix_path, vectors)
        try:
            import faiss

            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            faiss.write_index(index, str(self.index_path))
        except Exception:
            return

    def _load_vectors(self):
        if not self.matrix_path.is_file():
            return None
        import numpy as np

        return np.load(self.matrix_path)


def _embed(texts: list[str]):
    if not texts:
        return None
    # Hashing is the offline default. Set AQUAWATCH_EMBED=transformer to use
    # sentence-transformers, which must already be cached on disk.
    if os.environ.get("AQUAWATCH_EMBED") == "transformer":
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", local_files_only=True)
            vectors = model.encode(texts, normalize_embeddings=True)
            return vectors.astype("float32")
        except Exception:
            return _hash_embed(texts)
    return _hash_embed(texts)


def _hash_embed(texts: list[str]):
    import numpy as np

    width = 256
    vectors = np.zeros((len(texts), width), dtype="float32")
    for row, text in enumerate(texts):
        for token in _tokens(text):
            vectors[row, hash(token) % width] += 1
        norm = np.linalg.norm(vectors[row])
        if norm:
            vectors[row] /= norm
    return vectors


def _vector_search(passages, matrix, query, limit: int) -> list[dict]:
    try:
        import faiss

        index_path_holder = None
        del index_path_holder
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        _scores, ids = index.search(query.reshape(1, -1), min(limit, len(passages)))
        return [passages[int(item)] for item in ids[0] if item >= 0]
    except Exception:
        import numpy as np

        scores = matrix @ query
        order = np.argsort(scores)[::-1][:limit]
        return [passages[int(item)] for item in order if scores[int(item)] > 0]
