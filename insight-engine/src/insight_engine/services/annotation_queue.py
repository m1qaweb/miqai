import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any


class AnnotationQueue:
    """
    Manages a persistent queue of items for human annotation using SQLite.
    """

    def __init__(self, db_path: str = "annotation_queue.db"):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        """Creates the queue table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
                CREATE TABLE IF NOT EXISTS annotation_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metadata TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        )
        self.conn.commit()

    def add_item(self, item_metadata: Dict[str, Any]) -> int:
        """
        Adds a new item to the annotation queue.
        """
        metadata_str = json.dumps(item_metadata)
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO annotation_queue (metadata) VALUES (?)", (metadata_str,)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_items(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves a list of pending items from the queue.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, metadata, status, created_at FROM annotation_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        items = []
        for row in rows:
            items.append(
                {
                    "id": row[0],
                    "metadata": json.loads(row[1]),
                    "status": row[2],
                    "created_at": row[3],
                }
            )
        return items

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
