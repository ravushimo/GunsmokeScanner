"""SQLite persistence for scanned Growth Data cores (type + perks)."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.path.join("data", "inventory.db")

_CORE_DDL = """
CREATE TABLE IF NOT EXISTS growth_cores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    perk1_name TEXT NOT NULL,
    perk1_level INTEGER NOT NULL,
    perk2_name TEXT NOT NULL,
    perk2_level INTEGER NOT NULL,
    perk3_name TEXT,
    perk3_level INTEGER,
    quantity INTEGER NOT NULL DEFAULT 1,
    last_scanned_at TEXT,
    UNIQUE (
        type,
        perk1_name, perk1_level, perk2_name, perk2_level,
        perk3_name, perk3_level
    )
)
"""


class InventoryDB:
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
            conn.execute(_CORE_DDL)
            cols = {
                r[1]
                for r in conn.execute("PRAGMA table_info(growth_cores)").fetchall()
            }
            # Migrate icon_key / prefix_name schemas → type+perks only
            if "icon_key" in cols or "prefix_name" in cols:
                conn.execute(
                    "ALTER TABLE growth_cores RENAME TO growth_cores_legacy_identity"
                )
                conn.execute(_CORE_DDL)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT,
                    ended_at TEXT,
                    own_count_ocr INTEGER,
                    slots_scanned INTEGER,
                    slots_skipped_locked INTEGER,
                    notes TEXT
                )
                """
            )

    @staticmethod
    def _perk_key(perks: List[Dict]) -> Tuple:
        p1 = perks[0] if len(perks) > 0 else {}
        p2 = perks[1] if len(perks) > 1 else {}
        p3 = perks[2] if len(perks) > 2 else {}
        return (
            p1.get("name") or "",
            int(p1.get("level") or 0),
            p2.get("name") or "",
            int(p2.get("level") or 0),
            p3.get("name"),
            int(p3["level"]) if p3.get("name") and p3.get("level") else None,
        )

    def upsert_core(
        self,
        core_type: str,
        perks: List[Dict],
        *,
        scanned_at: Optional[str] = None,
    ) -> Tuple[bool, int]:
        """Insert or increment quantity. Returns (is_new_row, quantity)."""
        if scanned_at is None:
            scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if len(perks) < 2:
            raise ValueError("Need at least 2 perks")
        p1n, p1l, p2n, p2l, p3n, p3l = self._perk_key(perks)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, quantity FROM growth_cores
                WHERE type = ?
                  AND perk1_name = ? AND perk1_level = ?
                  AND perk2_name = ? AND perk2_level = ?
                  AND IFNULL(perk3_name, '') = IFNULL(?, '')
                  AND IFNULL(perk3_level, -1) = IFNULL(?, -1)
                """,
                (core_type, p1n, p1l, p2n, p2l, p3n, p3l),
            ).fetchone()
            if row:
                qty = int(row["quantity"]) + 1
                conn.execute(
                    """
                    UPDATE growth_cores
                    SET quantity = ?, last_scanned_at = ?
                    WHERE id = ?
                    """,
                    (qty, scanned_at, row["id"]),
                )
                return False, qty
            conn.execute(
                """
                INSERT INTO growth_cores (
                    type,
                    perk1_name, perk1_level, perk2_name, perk2_level,
                    perk3_name, perk3_level, quantity, last_scanned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (core_type, p1n, p1l, p2n, p2l, p3n, p3l, scanned_at),
            )
            return True, 1

    def list_cores(
        self, *, core_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM growth_cores"
        params: Tuple = ()
        if core_type:
            sql += " WHERE type = ?"
            params = (core_type,)
        sql += " ORDER BY type, perk1_name, perk2_name, perk3_name"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def total_quantity(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS n FROM growth_cores"
            ).fetchone()
            return int(row["n"] if row else 0)

    def unique_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM growth_cores"
            ).fetchone()
            return int(row["n"] if row else 0)

    def update_quantity(self, core_id: int, quantity: int) -> None:
        quantity = max(0, int(quantity))
        with self._connect() as conn:
            if quantity == 0:
                conn.execute("DELETE FROM growth_cores WHERE id = ?", (core_id,))
            else:
                conn.execute(
                    "UPDATE growth_cores SET quantity = ? WHERE id = ?",
                    (quantity, core_id),
                )

    def delete_core(self, core_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM growth_cores WHERE id = ?", (core_id,))

    def clear_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM growth_cores")

    def start_session(self, own_count_ocr: Optional[int] = None) -> int:
        started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO scan_sessions (
                    started_at, own_count_ocr, slots_scanned, slots_skipped_locked
                ) VALUES (?, ?, 0, 0)
                """,
                (started, own_count_ocr),
            )
            return int(cur.lastrowid)

    def end_session(
        self,
        session_id: int,
        *,
        slots_scanned: int,
        slots_skipped_locked: int,
        notes: str = "",
    ) -> None:
        ended = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE scan_sessions
                SET ended_at = ?, slots_scanned = ?, slots_skipped_locked = ?, notes = ?
                WHERE id = ?
                """,
                (ended, slots_scanned, slots_skipped_locked, notes, session_id),
            )
