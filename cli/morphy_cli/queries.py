"""Persistent saved queries manager for MORPHY CLI."""

import json
from pathlib import Path
import time
from typing import Any, Optional

CONFIG_DIR = Path.home() / ".morphy"
QUERIES_FILE = CONFIG_DIR / "queries.json"


class QueryStore:
    """Manages saved queries persisted in ~/.morphy/queries.json."""

    def __init__(self, filepath: Optional[Path] = None):
        self.filepath = filepath or QUERIES_FILE

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.filepath.is_file():
            return {}
        try:
            data = json.loads(self.filepath.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save(
        self,
        name: str,
        sql: str,
        database_id: Optional[str] = None,
        description: str = "",
    ) -> dict[str, Any]:
        """Save or update a query by name."""
        clean_name = name.strip()
        data = self._load()
        record = {
            "name": clean_name,
            "sql": sql.strip(),
            "database_id": database_id or "sample",
            "description": description.strip(),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        }
        data[clean_name] = record
        self._save(data)
        return record

    def list(self, database_id: Optional[str] = None) -> list[dict[str, Any]]:
        """List all saved queries, optionally filtered by database."""
        data = self._load()
        records = list(data.values())
        if database_id:
            records = [r for r in records if r.get("database_id") in (database_id, "sample")]
        records.sort(key=lambda r: r.get("name", ""))
        return records

    def get(self, name: str) -> Optional[dict[str, Any]]:
        """Retrieve a saved query by name."""
        data = self._load()
        return data.get(name.strip())

    def delete(self, name: str) -> bool:
        """Delete a saved query by name. Returns True if found and deleted."""
        clean_name = name.strip()
        data = self._load()
        if clean_name in data:
            del data[clean_name]
            self._save(data)
            return True
        return False
