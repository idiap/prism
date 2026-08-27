# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Read-only summaries for cataloged Open Agent Skills."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from prism.platform.specs.imported_skillset_specs import ImportedSkillSpec
from prism.platform.specs.skill_specs import SkillSpec


@dataclass(frozen=True, slots=True)
class CatalogSkillSummary:
    skill_id: str
    name: str
    version: str
    capability_type: str
    content_hash: str
    source_ecosystem: str


def native_skill_summary(skill: SkillSpec) -> CatalogSkillSummary:
    return _summary(
        skill.spec_id,
        skill.name,
        skill.version,
        "prism-platform",
        skill.model_dump(mode="json"),
    )


def imported_skill_summary(skill: ImportedSkillSpec) -> CatalogSkillSummary:
    return _summary(
        skill.import_id,
        skill.name,
        skill.version,
        skill.source_project,
        skill.model_dump(mode="json"),
    )


def _summary(
    skill_id: str,
    name: str,
    version: str,
    ecosystem: str,
    payload: object,
) -> CatalogSkillSummary:
    stable = "".join(
        item[:1].upper() + item[1:]
        for item in skill_id.replace("_", "-").split("-")
        if item
    )
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return CatalogSkillSummary(
        skill_id,
        name,
        version,
        f"{stable or 'Imported'}Task",
        f"sha256:{digest}",
        ecosystem,
    )


__all__ = ["CatalogSkillSummary", "imported_skill_summary", "native_skill_summary"]
