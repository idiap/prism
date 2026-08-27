# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from pathlib import Path

from prism.platform.domain.events import EventRecord
from prism.platform.infra.event_store import EventStore


def test_event_store_appends_and_lists_events_in_order(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events")
    first = EventRecord(
        event_id="event_1",
        run_id="run_1",
        event_type="task.started",
        actor="scheduler",
        timestamp="2026-03-19T12:00:00+00:00",
        payload={"task_id": "task_1"},
    )
    second = EventRecord(
        event_id="event_2",
        run_id="run_1",
        event_type="task.completed",
        actor="solver",
        timestamp="2026-03-19T12:01:00+00:00",
        payload={"task_id": "task_1"},
    )

    store.append(first)
    store.append(second)

    listed = store.list()

    assert [event.event_id for event in listed] == ["event_1", "event_2"]
    assert listed[1].payload["task_id"] == "task_1"
