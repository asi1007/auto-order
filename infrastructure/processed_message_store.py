from __future__ import annotations

import json
from pathlib import Path

_STATE_KEY = "processed_message_ids"


class ProcessedMessageStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def is_processed(self, message_id: str) -> bool:
        return str(message_id) in self._load()

    def mark_processed(self, message_ids: list[str]) -> None:
        known = self._load()
        for message_id in message_ids:
            if str(message_id) not in known:
                known.append(str(message_id))
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({_STATE_KEY: known}, ensure_ascii=False, indent=2))

    def _load(self) -> list[str]:
        if not self._path.exists():
            return []
        return list(json.loads(self._path.read_text()).get(_STATE_KEY, []))
