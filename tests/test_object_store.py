# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from pathlib import Path

from prism.platform.domain.artifacts import ArtifactOrigin, ArtifactVersion
from prism.platform.domain.enums import ArtifactStatus
from prism.platform.infra.object_store import ObjectStore


def test_object_store_round_trips_artifacts(tmp_path: Path) -> None:
    store = ObjectStore(tmp_path / "objects")
    artifact = ArtifactVersion(
        oid="artifact_1",
        vid="artifact_v1",
        kind="summary",
        payload={"summary": "stored"},
        origin=ArtifactOrigin(run_id="run_1", spec_id="skill_1"),
        status=ArtifactStatus.ACCEPTED,
        created_at="2026-03-19T12:00:00+00:00",
    )

    store.put(artifact)
    loaded = store.get("artifact_v1")

    assert loaded == artifact
