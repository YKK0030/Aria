from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from typing import Any

from agent_core.config import settings


class SQLiteLongTermGraphMemory:
    def __init__(self) -> None:
        self._path = settings.resolved_long_term_memory_db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_enabled = False
        self._initialize()

    def add_node(
        self,
        channel: str,
        chat_id: str,
        role: str,
        text: str,
        source_message_id: str | None = None,
    ) -> int | None:
        if not text.strip():
            return None

        try:
            with self._connect() as connection:
                previous_node_id = self._get_latest_node_id(connection, channel, chat_id)
                cursor = connection.execute(
                    """
                    INSERT INTO memory_nodes (channel, chat_id, role, text, source_message_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (channel, chat_id, role, text, source_message_id, datetime.now(UTC).isoformat()),
                )
                node_id = int(cursor.lastrowid)

                if self._fts_enabled:
                    connection.execute(
                        """
                        INSERT INTO memory_nodes_fts (rowid, channel, chat_id, role, text)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (node_id, channel, chat_id, role, text),
                    )

                if previous_node_id:
                    self._add_edge(connection, previous_node_id, node_id, "sequence", 1.0)

                connection.commit()
                return node_id
        except Exception:
            return None

    def add_edge(self, from_node_id: int, to_node_id: int, edge_type: str, weight: float = 1.0) -> None:
        try:
            with self._connect() as connection:
                self._add_edge(connection, from_node_id, to_node_id, edge_type, weight)
                connection.commit()
        except Exception:
            return

    def retrieve_top_nodes(self, channel: str, chat_id: str, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        top_k = limit or settings.long_term_memory_top_k
        top_k = max(1, min(top_k, 6))

        try:
            with self._connect() as connection:
                if self._fts_enabled:
                    search_terms = self._build_fts_query(query)
                    if search_terms:
                        rows = connection.execute(
                            """
                            SELECT
                                memory_nodes.id,
                                memory_nodes.role,
                                memory_nodes.text,
                                memory_nodes.created_at,
                                memory_nodes.source_message_id,
                                bm25(memory_nodes_fts) AS score
                            FROM memory_nodes_fts
                            JOIN memory_nodes ON memory_nodes.id = memory_nodes_fts.rowid
                            WHERE memory_nodes_fts MATCH ?
                              AND memory_nodes.channel = ?
                              AND memory_nodes.chat_id = ?
                            ORDER BY score ASC, memory_nodes.id DESC
                            LIMIT ?
                            """,
                            (search_terms, channel, chat_id, top_k),
                        ).fetchall()
                        if rows:
                            return [self._row_to_dict(row) for row in rows]

                rows = connection.execute(
                    """
                    SELECT id, role, text, created_at, source_message_id, 0.0 AS score
                    FROM memory_nodes
                    WHERE channel = ? AND chat_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (channel, chat_id, top_k),
                ).fetchall()
                return [self._row_to_dict(row) for row in rows]
        except Exception:
            return []

    def search_nodes(self, channel: str, chat_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        if not query.strip():
            return self.get_chat_graph(channel, chat_id, limit).get("nodes", [])
        try:
            with self._connect() as connection:
                if self._fts_enabled:
                    search_terms = self._build_fts_query(query)
                    if search_terms:
                        rows = connection.execute(
                            """
                            SELECT
                                memory_nodes.id,
                                memory_nodes.role,
                                memory_nodes.text,
                                memory_nodes.created_at,
                                memory_nodes.source_message_id,
                                bm25(memory_nodes_fts) AS score
                            FROM memory_nodes_fts
                            JOIN memory_nodes ON memory_nodes.id = memory_nodes_fts.rowid
                            WHERE memory_nodes_fts MATCH ?
                              AND memory_nodes.channel = ?
                              AND memory_nodes.chat_id = ?
                            ORDER BY score ASC, memory_nodes.id DESC
                            LIMIT ?
                            """,
                            (search_terms, channel, chat_id, limit),
                        ).fetchall()
                        if rows:
                            return [self._row_to_dict(row) for row in rows]

                rows = connection.execute(
                    """
                    SELECT id, role, text, created_at, source_message_id, 0.0 AS score
                    FROM memory_nodes
                    WHERE channel = ? AND chat_id = ? AND text LIKE ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (channel, chat_id, f"%{query}%", limit),
                ).fetchall()
                return [self._row_to_dict(row) for row in rows]
        except Exception:
            return []

    def get_node_details(self, node_id: int) -> dict[str, Any] | None:
        try:
            with self._connect() as connection:
                node = connection.execute(
                    """
                    SELECT id, channel, chat_id, role, text, source_message_id, created_at
                    FROM memory_nodes
                    WHERE id = ?
                    """,
                    (node_id,),
                ).fetchone()
                if not node:
                    return None

                outgoing = connection.execute(
                    """
                    SELECT
                        memory_edges.id,
                        memory_edges.edge_type,
                        memory_edges.weight,
                        memory_edges.to_node_id AS related_node_id,
                        memory_nodes.role AS related_role,
                        memory_nodes.text AS related_text,
                        memory_nodes.created_at AS related_created_at
                    FROM memory_edges
                    JOIN memory_nodes ON memory_nodes.id = memory_edges.to_node_id
                    WHERE memory_edges.from_node_id = ?
                    ORDER BY memory_edges.id DESC
                    LIMIT 25
                    """,
                    (node_id,),
                ).fetchall()

                incoming = connection.execute(
                    """
                    SELECT
                        memory_edges.id,
                        memory_edges.edge_type,
                        memory_edges.weight,
                        memory_edges.from_node_id AS related_node_id,
                        memory_nodes.role AS related_role,
                        memory_nodes.text AS related_text,
                        memory_nodes.created_at AS related_created_at
                    FROM memory_edges
                    JOIN memory_nodes ON memory_nodes.id = memory_edges.from_node_id
                    WHERE memory_edges.to_node_id = ?
                    ORDER BY memory_edges.id DESC
                    LIMIT 25
                    """,
                    (node_id,),
                ).fetchall()

                return {
                    "node": {
                        "id": int(node["id"]),
                        "channel": node["channel"],
                        "chat_id": node["chat_id"],
                        "role": node["role"],
                        "text": node["text"],
                        "source_message_id": node["source_message_id"],
                        "created_at": node["created_at"],
                    },
                    "outgoing": [self._edge_row_to_dict(row) for row in outgoing],
                    "incoming": [self._edge_row_to_dict(row) for row in incoming],
                }
        except Exception:
            return None

    def get_chat_graph(self, channel: str, chat_id: str, limit: int = 50) -> dict[str, Any]:
        limit = max(1, min(limit, 200))
        try:
            with self._connect() as connection:
                nodes = connection.execute(
                    """
                    SELECT id, channel, chat_id, role, text, source_message_id, created_at
                    FROM memory_nodes
                    WHERE channel = ? AND chat_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (channel, chat_id, limit),
                ).fetchall()
                node_ids = [int(row["id"]) for row in nodes]
                if not node_ids:
                    return {"nodes": [], "edges": []}

                placeholders = ",".join("?" for _ in node_ids)
                edges = connection.execute(
                    f"""
                    SELECT id, from_node_id, to_node_id, edge_type, weight, created_at
                    FROM memory_edges
                    WHERE from_node_id IN ({placeholders}) OR to_node_id IN ({placeholders})
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (*node_ids, *node_ids, limit * 2),
                ).fetchall()

                return {
                    "nodes": [
                        {
                            "id": int(row["id"]),
                            "channel": row["channel"],
                            "chat_id": row["chat_id"],
                            "role": row["role"],
                            "text": row["text"],
                            "source_message_id": row["source_message_id"],
                            "created_at": row["created_at"],
                        }
                        for row in nodes
                    ],
                    "edges": [
                        {
                            "id": int(row["id"]),
                            "from_node_id": int(row["from_node_id"]),
                            "to_node_id": int(row["to_node_id"]),
                            "edge_type": row["edge_type"],
                            "weight": float(row["weight"]),
                            "created_at": row["created_at"],
                        }
                        for row in edges
                    ],
                }
        except Exception:
            return {"nodes": [], "edges": []}

    def _initialize(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_nodes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        channel TEXT NOT NULL,
                        chat_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        text TEXT NOT NULL,
                        source_message_id TEXT,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_edges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        from_node_id INTEGER NOT NULL,
                        to_node_id INTEGER NOT NULL,
                        edge_type TEXT NOT NULL,
                        weight REAL NOT NULL DEFAULT 1.0,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memory_nodes_chat ON memory_nodes(channel, chat_id, id DESC)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memory_edges_nodes ON memory_edges(from_node_id, to_node_id)"
                )
                try:
                    connection.execute(
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS memory_nodes_fts
                        USING fts5(channel, chat_id, role, text)
                        """
                    )
                    self._fts_enabled = True
                except sqlite3.OperationalError:
                    self._fts_enabled = False
                connection.commit()
        except Exception:
            self._fts_enabled = False

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _get_latest_node_id(connection: sqlite3.Connection, channel: str, chat_id: str) -> int | None:
        row = connection.execute(
            """
            SELECT id
            FROM memory_nodes
            WHERE channel = ? AND chat_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (channel, chat_id),
        ).fetchone()
        if not row:
            return None
        return int(row["id"])

    @staticmethod
    def _add_edge(
        connection: sqlite3.Connection,
        from_node_id: int,
        to_node_id: int,
        edge_type: str,
        weight: float,
    ) -> None:
        connection.execute(
            """
            INSERT INTO memory_edges (from_node_id, to_node_id, edge_type, weight, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (from_node_id, to_node_id, edge_type, weight, datetime.now(UTC).isoformat()),
        )

    @staticmethod
    def _build_fts_query(text: str) -> str:
        terms = re.findall(r"[A-Za-z0-9_]{2,}", text.lower())
        unique_terms: list[str] = []
        for term in terms:
            if term not in unique_terms:
                unique_terms.append(term)
        return " OR ".join(unique_terms[:10])

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        score = float(row["score"]) if "score" in row.keys() else 0.0
        normalized_score = 1.0 / (1.0 + abs(score))
        return {
            "id": int(row["id"]),
            "role": row["role"],
            "text": row["text"],
            "created_at": row["created_at"],
            "source_message_id": row["source_message_id"],
            "score": normalized_score,
        }

    @staticmethod
    def _edge_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "edge_type": row["edge_type"],
            "weight": float(row["weight"]),
            "related_node_id": int(row["related_node_id"]),
            "related_role": row["related_role"],
            "related_text": row["related_text"],
            "related_created_at": row["related_created_at"],
        }


long_term_memory = SQLiteLongTermGraphMemory()
