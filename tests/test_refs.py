# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from prism.platform.domain.artifacts import ArtifactOrigin, ArtifactVersion
from prism.platform.domain.enums import ArtifactStatus
from prism.platform.domain.refs import ArtifactRef


def test_artifact_ref_round_trip_from_artifact_version() -> None:
    artifact = ArtifactVersion(
        oid="artifact_1",
        vid="artifact_v1",
        kind="analysis",
        payload={"summary": "ok"},
        origin=ArtifactOrigin(run_id="run_1"),
        status=ArtifactStatus.ACCEPTED,
        created_at="2026-03-19T12:00:00+00:00",
    )

    ref = artifact.ref()

    assert ref == ArtifactRef(oid="artifact_1", vid="artifact_v1", kind="analysis")
