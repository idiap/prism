# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""YAML loader helpers used by capability index construction."""

from __future__ import annotations

# Platform-only capability schemas.
from pathlib import Path
from typing import Iterable

import yaml


def iter_yaml_files(root: Path) -> Iterable[Path]:
    """Yield all YAML files below a root in stable sorted order."""
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.yaml") if path.is_file())


def load_yaml(path: Path) -> dict:
    """Load one YAML mapping and reject non-mapping top-level documents."""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML document at {path} must be a mapping")
    return data
