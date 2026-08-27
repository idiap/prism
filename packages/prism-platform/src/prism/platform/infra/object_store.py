# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform storage for immutable artifact versions."""

from __future__ import annotations

import json
from pathlib import Path

from prism.platform.domain.artifacts import ArtifactVersion


class ObjectStore:
    """Persist artifact versions as individual JSON files."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, artifact: ArtifactVersion) -> None:
        """Write one artifact version to the object store."""
        path = self.root / f"{artifact.vid}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(
                artifact.model_dump(mode="json"), handle, ensure_ascii=True, indent=2
            )

    def get(self, vid: str) -> ArtifactVersion:
        """Load one artifact version by version id."""
        path = self.root / f"{vid}.json"
        with path.open("r", encoding="utf-8") as handle:
            return ArtifactVersion.model_validate(json.load(handle))
