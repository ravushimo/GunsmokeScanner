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

    def insert_pulls(self, pulls: Iterable[Dict[str, Any]]) -> Tuple[int, int]:
        """Bulk insert. Returns (inserted, updated_or_skipped).

        On duplicate (time, name, ordinal), refresh source/type/rarity so a
        re-scan can fix cleaned fields without creating a second row.
        """
        inserted = 0
        skipped = 0
        scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            for p in pulls:
                cur = conn.execute(
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
                        p["purchase_time"],
                        p["purchase_source"],
                        p["item_type"],
                        p["item_name"],
                        p.get("ordinal", 0),
                        p.get("rarity_color"),
                        p.get("scanned_at", scanned_at),
                    ),
                )
                # rowcount is 1 for insert; SQLite may report 1 for update too
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
        return inserted, skipped

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
