from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class TraceWriter:
    def __init__(self, path: Path):
        self.path = path

    def reset(self) -> None:
        self.path.write_text("", encoding="utf-8")

    def write(self, case_id: str, agent: str, event: str, summary: dict | None = None) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case_id": case_id,
            "agent": agent,
            "event": event,
            "summary": summary or {},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

