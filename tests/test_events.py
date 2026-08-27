# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from prism.platform.domain.events import EventRecord


def test_event_record_stores_payload_and_optional_links() -> None:
    event = EventRecord(
        event_id="event_1",
        run_id="run_1",
        event_type="task.completed",
        actor="solver",
        timestamp="2026-03-19T12:00:00+00:00",
        causation_id="cause_1",
        correlation_id="corr_1",
        payload={"task_id": "task_1", "status": "done"},
    )

    assert event.payload["task_id"] == "task_1"
    assert event.causation_id == "cause_1"
    assert event.correlation_id == "corr_1"
