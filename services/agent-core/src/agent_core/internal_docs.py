from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_core.config import settings

logger = logging.getLogger(__name__)

MAX_FILES = 1000
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 20_000_000
CHUNK_CHARS = 1200
TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
STOP_WORDS = {"about", "after", "also", "and", "are", "can", "for", "from", "how", "into", "its", "not", "our", "the", "this", "that", "then", "was", "what", "when", "where", "with", "you"}


@dataclass(frozen=True)
class DocChunk:
    path: str
    title: str
    line_start: int
    line_end: int
    text: str
    tokens: tuple[str, ...]


class InternalDocsIndex:
    """Read-only lexical retrieval over repository Markdown and text docs."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.resolved_docs_dir
        self._signature: tuple[tuple[str, int, int], ...] | None = None
        self._chunks: list[DocChunk] = []

    def reindex(self) -> dict[str, int]:
        self._signature = None
        self._refresh()
        return {
            "files": len({chunk.path for chunk in self._chunks}),
            "chunks": len(self._chunks),
        }

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            return []
        self._refresh()
        terms = [term for term in TOKEN_RE.findall(query.lower()) if term not in STOP_WORDS]
        if not terms or not self._chunks:
            return []
        limit = max(1, min(int(limit), 10))
        document_frequency: dict[str, int] = {}
        for chunk in self._chunks:
            for term in set(chunk.tokens):
                document_frequency[term] = document_frequency.get(term, 0) + 1
        average_length = sum(len(chunk.tokens) for chunk in self._chunks) / len(self._chunks)
        ranked: list[tuple[float, DocChunk]] = []
        for chunk in self._chunks:
            counts: dict[str, int] = {}
            for token in chunk.tokens:
                counts[token] = counts.get(token, 0) + 1
            length = len(chunk.tokens)
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                df = document_frequency.get(term, 0)
                inverse = math.log(1 + (len(self._chunks) - df + 0.5) / (df + 0.5))
                score += inverse * (frequency * 2.2) / (
                    frequency + 1.2 * (0.25 + 0.75 * length / max(average_length, 1))
                )
            if score:
                ranked.append((score, chunk))
        ranked.sort(key=lambda item: (-item[0], item[1].path, item[1].line_start))
        return [
            {
                "title": chunk.title,
                "path": chunk.path,
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
                "citation": f"[{chunk.path}:L{chunk.line_start}-L{chunk.line_end}]",
                "score": round(score, 4),
                "snippet": chunk.text[:900],
            }
            for score, chunk in ranked[:limit]
        ]

    def _refresh(self) -> None:
        if self.root.is_symlink() or not self.root.is_dir():
            self._chunks = []
            self._signature = ()
            return
        files = sorted(
            path for path in self.root.rglob("*")
            if path.suffix.lower() in {".md", ".txt"}
            and not path.is_symlink()
            and path.is_file()
            and path.resolve().is_relative_to(self.root.resolve())
        )[:MAX_FILES]
        signature_items = []
        total_bytes = 0
        for path in files:
            size = path.stat().st_size
            if size > MAX_FILE_BYTES or total_bytes + size > MAX_TOTAL_BYTES:
                continue
            total_bytes += size
            signature_items.append((path.relative_to(self.root).as_posix(), path.stat().st_mtime_ns, size))
        signature = tuple(signature_items)
        if signature == self._signature:
            return
        chunks: list[DocChunk] = []
        for path in files:
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            chunks.extend(self._split(path, text))
        self._chunks = chunks
        self._signature = signature
        logger.info("Indexed %d internal documentation chunks from %d files", len(chunks), len(signature))

    def _split(self, path: Path, text: str) -> list[DocChunk]:
        lines = text.splitlines()
        if not lines:
            return []
        title = next((line.lstrip("# ").strip() for line in lines if line.startswith("# ")), path.stem)
        output: list[DocChunk] = []
        current: list[str] = []
        start_line = 1
        current_size = 0

        def add_chunk(end_line: int) -> None:
            content = "\n".join(current).strip()
            tokens = tuple(TOKEN_RE.findall(content.lower()))
            if tokens:
                output.append(DocChunk(
                    path=path.relative_to(self.root).as_posix(), title=title,
                    line_start=start_line, line_end=end_line, text=content, tokens=tokens,
                ))

        current_end_line = 1
        for line_number, line in enumerate(lines, start=1):
            segments = [line[offset:offset + CHUNK_CHARS] for offset in range(0, len(line), CHUNK_CHARS)] or [""]
            for segment in segments:
                if current and current_size + len(segment) + 1 > CHUNK_CHARS:
                    add_chunk(current_end_line)
                    current = []
                    start_line = line_number
                    current_size = 0
                current.append(segment)
                current_size += len(segment) + 1
                current_end_line = line_number
        if current:
            add_chunk(len(lines))
        return output


internal_docs = InternalDocsIndex()
