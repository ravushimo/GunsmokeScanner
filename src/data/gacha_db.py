"""SQLite persistence for Access Records pulls."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

DB_PATH = os.path.join("data", "gacha.db")


class GachaDB:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pulls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchase_time TEXT NOT NULL,
                    purchase_source TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    ordinal INTEGER NOT NULL DEFAULT 0,
                    rarity_color TEXT,
                    scanned_at TEXT NOT NULL,
                    UNIQUE (purchase_time, item_name, ordinal)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pulls_time ON pulls(purchase_time DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pulls_source ON pulls(purchase_source)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_overrides (
                    item_name TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    copies INTEGER NOT NULL,
                    PRIMARY KEY (item_name, item_type)
                )
                """
            )

    def insert_pull(
        self,
        purchase_time: str,
        purchase_source: str,
        item_type: str,
        item_name: str,
        ordinal: int,
        rarity_color: Optional[str] = None,
        scanned_at: Optional[str] = None,
    ) -> bool:
        """Insert a pull. Returns True if inserted, False if duplicate."""
        if scanned_at is None:
            scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO pulls (
                    purchase_time, purchase_source, item_type, item_name,
                    ordinal, rarity_color, scanned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    purchase_time,
                    purchase_source,
                    item_type,
                    item_name,
                    ordinal,
                    rarity_color,
                    scanned_at,
                ),
            )
            return cur.rowcount > 0

    def pull_exists(
        self,
        purchase_time: str,
        item_name: str,
        ordinal: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        sql = """
            SELECT 1 FROM pulls
            WHERE purchase_time = ? AND item_name = ? AND ordinal = ?
            LIMIT 1
        """
        params = (purchase_time, item_name, ordinal)
        if conn is not None:
            return conn.execute(sql, params).fetchone() is not None
        with self._connect() as c:
            return c.execute(sql, params).fetchone() is not None

    def insert_pulls(self, pulls: Iterable[Dict[str, Any]]) -> Tuple[int, int]:
        """Bulk insert. Returns (inserted_new, already_known).

        Existing rows (same time, name, ordinal) are updated in place and
        counted as already_known so the scanner can stop when catching up.
        """
        inserted = 0
        known = 0
        scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            for p in pulls:
                time_s = p["purchase_time"]
                name = p["item_name"]
                ordinal = int(p.get("ordinal", 0))
                existed = self.pull_exists(time_s, name, ordinal, conn=conn)
                conn.execute(
                    """
                    INSERT INTO pulls (
                        purchase_time, purchase_source, item_type, item_name,
                        ordinal, rarity_color, scanned_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(purchase_time, item_name, ordinal) DO UPDATE SET
                        purchase_source = excluded.purchase_source,
                        item_type = excluded.item_type,
                        rarity_color = excluded.rarity_color,
                        scanned_at = excluded.scanned_at
                    """,
                    (
                        time_s,
                        p["purchase_source"],
                        p["item_type"],
                        name,
                        ordinal,
                        p.get("rarity_color"),
                        p.get("scanned_at", scanned_at),
                    ),
                )
                if existed:
                    known += 1
                else:
                    inserted += 1
        return inserted, known

    def list_pulls(
        self,
        purchase_source: Optional[str] = None,
        item_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 5000,
        oldest_first: bool = False,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if purchase_source:
            clauses.append("purchase_source = ?")
            params.append(purchase_source)
        if item_type:
            clauses.append("item_type = ?")
            params.append(item_type)
        if date_from:
            clauses.append("purchase_time >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("purchase_time <= ?")
            params.append(date_to)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        # Access Records are scanned page 1 → N (newest → oldest), so lower
        # autoincrement id means newer within the same purchase_time second.
        # Oldest→newest pity timeline must reverse that: time ASC, id DESC.
        # Newest→oldest UI order matches scan order: time DESC, id ASC.
        order = (
            "ORDER BY purchase_time ASC, id DESC"
            if oldest_first
            else "ORDER BY purchase_time DESC, id ASC"
        )
        sql = f"""
            SELECT id, purchase_time, purchase_source, item_type, item_name,
                   ordinal, rarity_color, scanned_at
            FROM pulls
            {where}
            {order}
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def list_all_oldest_first(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 20000,
    ) -> List[Dict[str, Any]]:
        """Full timeline for pity/index annotation (oldest → newest)."""
        return self.list_pulls(
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            oldest_first=True,
        )

    def distinct_sources(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT purchase_source FROM pulls ORDER BY purchase_source"
            ).fetchall()
        return [r[0] for r in rows]

    def count_pulls(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM pulls").fetchone()
        return int(row[0]) if row else 0

    def clear_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM pulls")

    def normalize_purchase_sources(self) -> int:
        """Rewrite OCR-mangled purchase_source values to canonical names.

        Returns how many rows were updated.
        """
        from src.core.gacha_scanner import clean_source

        updated = 0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT purchase_source FROM pulls"
            ).fetchall()
            for (raw,) in rows:
                canon = clean_source(raw)
                if not canon or canon == raw:
                    continue
                cur = conn.execute(
                    "UPDATE pulls SET purchase_source = ? WHERE purchase_source = ?",
                    (canon, raw),
                )
                updated += cur.rowcount
        return updated

    def distinct_item_names(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT item_name FROM pulls ORDER BY item_name"
            ).fetchall()
        return [r[0] for r in rows if r[0]]

    def distinct_item_name_types(self) -> List[Tuple[str, str]]:
        """Distinct (item_name, item_type) pairs for type-aware OCR repair."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT item_name, item_type
                FROM pulls
                ORDER BY item_type, item_name
                """
            ).fetchall()
        return [(r[0], r[1] or "") for r in rows if r[0]]

    def rename_item_name(
        self,
        old_name: str,
        new_name: str,
        item_type: Optional[str] = None,
    ) -> int:
        """Rename pulls with old_name → new_name.

        When item_type is set, only rows of that type are updated (required when
        dolls and weapons share a stem).
        """
        if not old_name or not new_name or old_name == new_name:
            return 0
        with self._connect() as conn:
            if item_type:
                conflict_sql = """
                    SELECT p.id, p.purchase_time, p.ordinal
                    FROM pulls p
                    WHERE p.item_name = ? AND p.item_type = ?
                      AND EXISTS (
                        SELECT 1 FROM pulls q
                        WHERE q.purchase_time = p.purchase_time
                          AND q.item_name = ?
                          AND q.ordinal = p.ordinal
                          AND q.id != p.id
                      )
                """
                conflict_params = (old_name, item_type, new_name)
            else:
                conflict_sql = """
                    SELECT p.id, p.purchase_time, p.ordinal
                    FROM pulls p
                    WHERE p.item_name = ?
                      AND EXISTS (
                        SELECT 1 FROM pulls q
                        WHERE q.purchase_time = p.purchase_time
                          AND q.item_name = ?
                          AND q.ordinal = p.ordinal
                          AND q.id != p.id
                      )
                """
                conflict_params = (old_name, new_name)

            conflicts = conn.execute(conflict_sql, conflict_params).fetchall()
            for row_id, purchase_time, ordinal in conflicts:
                new_ord = int(ordinal)
                while True:
                    new_ord += 1
                    exists = conn.execute(
                        """
                        SELECT 1 FROM pulls
                        WHERE purchase_time = ? AND item_name = ? AND ordinal = ?
                        LIMIT 1
                        """,
                        (purchase_time, new_name, new_ord),
                    ).fetchone()
                    if not exists:
                        break
                conn.execute(
                    "UPDATE pulls SET ordinal = ? WHERE id = ?",
                    (new_ord, row_id),
                )

            if item_type:
                cur = conn.execute(
                    "UPDATE pulls SET item_name = ? WHERE item_name = ? AND item_type = ?",
                    (new_name, old_name, item_type),
                )
                conn.execute(
                    """
                    UPDATE OR IGNORE collection_overrides
                    SET item_name = ? WHERE item_name = ? AND item_type = ?
                    """,
                    (new_name, old_name, item_type),
                )
                conn.execute(
                    "DELETE FROM collection_overrides WHERE item_name = ? AND item_type = ?",
                    (old_name, item_type),
                )
            else:
                cur = conn.execute(
                    "UPDATE pulls SET item_name = ? WHERE item_name = ?",
                    (new_name, old_name),
                )
                conn.execute(
                    """
                    UPDATE OR IGNORE collection_overrides
                    SET item_name = ? WHERE item_name = ?
                    """,
                    (new_name, old_name),
                )
                conn.execute(
                    "DELETE FROM collection_overrides WHERE item_name = ?",
                    (old_name,),
                )
            return int(cur.rowcount)

    def apply_name_fixes(self, pairs: List[Tuple[str, str, str]]) -> int:
        """Apply (old, new, item_type) renames. Returns total rows updated."""
        total = 0
        for old, new, item_type in pairs:
            total += self.rename_item_name(old, new, item_type=item_type or None)
        return total

    def get_collection_overrides(self) -> Dict[Tuple[str, str], int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT item_name, item_type, copies FROM collection_overrides"
            ).fetchall()
        return {(r[0], r[1]): int(r[2]) for r in rows}

    def set_collection_override(
        self, item_name: str, item_type: str, copies: int
    ) -> None:
        copies = max(0, min(7, int(copies)))
        with self._connect() as conn:
            if copies <= 0:
                conn.execute(
                    "DELETE FROM collection_overrides WHERE item_name = ? AND item_type = ?",
                    (item_name, item_type),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO collection_overrides (item_name, item_type, copies)
                    VALUES (?, ?, ?)
                    ON CONFLICT(item_name, item_type) DO UPDATE SET copies = excluded.copies
                    """,
                    (item_name, item_type, copies),
                )

    def clear_collection_override(self, item_name: str, item_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM collection_overrides WHERE item_name = ? AND item_type = ?",
                (item_name, item_type),
            )
