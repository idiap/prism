# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform project-layout helpers for Prism domain libraries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PrismProjectLayout:
    """Centralized access to library roots and manifests."""

    project_root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_root", self.project_root.resolve())

    @property
    def libs_root(self) -> Path:
        return self.project_root / "libs"

    def iter_library_manifests(self) -> list[Path]:
        """Return library manifests in deterministic domain order."""
        if not self.libs_root.exists():
            return []
        return sorted(
            path for path in self.libs_root.glob("*/library.yaml") if path.is_file()
        )
