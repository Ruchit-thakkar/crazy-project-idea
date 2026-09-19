"""SQLite database management for MediaDrop history and state."""

import sqlite3
from pathlib import Path
from typing import List, Optional

from app.database.models import HistoryRecord
from app.utils.logger import logger


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # Store in project directory
            db_path = Path(__file__).resolve().parent.parent.parent / "mediadrop.db"
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        format_type TEXT NOT NULL,
                        quality TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'Completed',
                        thumbnail_url TEXT DEFAULT '',
                        downloaded_at TEXT NOT NULL
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_date ON history(downloaded_at DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_platform ON history(platform)")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def add_history(self, record: HistoryRecord) -> int:
        """Insert a download record into history."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO history (
                        title, url, platform, format_type, quality,
                        file_path, file_size, status, thumbnail_url, downloaded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.title,
                    record.url,
                    record.platform,
                    record.format_type,
                    record.quality,
                    record.file_path,
                    record.file_size,
                    record.status,
                    record.thumbnail_url,
                    record.downloaded_at,
                ))
                conn.commit()
                return cursor.lastrowid or 0
        except Exception as e:
            logger.error(f"Failed to insert history record: {e}")
            return 0

    def get_history(
        self,
        search: str = "",
        platform: str = "",
        limit: int = 150
    ) -> List[HistoryRecord]:
        """Query history with optional search query and platform filter."""
        records: List[HistoryRecord] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM history WHERE 1=1"
                params = []

                if search.strip():
                    query += " AND (title LIKE ? OR url LIKE ?)"
                    term = f"%{search.strip()}%"
                    params.extend([term, term])

                if platform and platform != "All Platforms":
                    query += " AND platform = ?"
                    params.append(platform)

                query += " ORDER BY id DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                for row in cursor.fetchall():
                    records.append(HistoryRecord(
                        id=row["id"],
                        title=row["title"],
                        url=row["url"],
                        platform=row["platform"],
                        format_type=row["format_type"],
                        quality=row["quality"],
                        file_path=row["file_path"],
                        file_size=row["file_size"],
                        status=row["status"],
                        thumbnail_url=row["thumbnail_url"],
                        downloaded_at=row["downloaded_at"],
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch history: {e}")
        return records

    def delete_history(self, record_id: int) -> bool:
        """Delete a single history record."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM history WHERE id = ?", (record_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete history record {record_id}: {e}")
            return False

    def clear_all_history(self) -> bool:
        """Clear all records in the history table."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM history")
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            return False


# Singleton database instance
db = Database()
