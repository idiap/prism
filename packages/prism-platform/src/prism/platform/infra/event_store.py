# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform append-only event storage."""

from __future__ import annotations

import json
from pathlib import Path

from prism.platform.domain.events import EventRecord


class EventStore:
    """Persist and reload event records for a run."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "events.jsonl"

    def append(self, event: EventRecord) -> None:
        """Append one event record to the JSONL event log."""
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(event.model_dump(mode="json"), ensure_ascii=True) + "\n"
            )

    def list(self) -> list[EventRecord]:
        """Load all persisted event records in append order."""
        if not self.path.exists():
            return []
        events: list[EventRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    events.append(EventRecord.model_validate_json(line))
        return events
