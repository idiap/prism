# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Strict source discovery for Open Agent Skills and native hook configs."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SCRIPT_SUFFIXES = frozenset({".py", ".sh", ".bash", ".zsh", ".js", ".ts", ".rb", ".pl"})


@dataclass(frozen=True, slots=True)
class BuildObligation:
    element: str
    details: str


@dataclass(frozen=True, slots=True)
class DiscoveredSkill:
    root: Path
    instruction_file: Path
    source_files: tuple[Path, ...]
    skill_id: str
    version: str
    name: str
    description: str
    instructions: str
    obligations: tuple[BuildObligation, ...]


def discover_skills(source_root: Path) -> tuple[DiscoveredSkill, ...]:
    if source_root.is_file():
        candidates = (source_root,) if source_root.name == "SKILL.md" else ()
    else:
        candidates = tuple(sorted(source_root.rglob("SKILL.md")))
    roots = {path.parent for path in candidates}
    discovered: list[DiscoveredSkill] = []
    for instruction_file in candidates:
        root = instruction_file.parent
        metadata, body = parse_frontmatter(instruction_file.read_text(encoding="utf-8"))
        source_files = tuple(
            path
            for path in sorted(root.rglob("*"))
            if path.is_file()
            and not path.is_symlink()
            and not any(
                nested != root and path.is_relative_to(nested) for nested in roots
            )
        )
        obligations: list[BuildObligation] = []
        for path in source_files:
            relative = path.relative_to(root).as_posix()
            if _credential_file(path):
                obligations.append(
                    BuildObligation(
                        relative,
                        "credential-shaped files cannot be embedded in a skill module",
                    )
                )
            elif path.suffix.lower() in SCRIPT_SUFFIXES:
                obligations.append(
                    BuildObligation(
                        relative,
                        "bundled scripts require a separately exported typed Tool contract",
                    )
                )
        if not body.strip():
            obligations.append(
                BuildObligation("SKILL.md", "the Markdown instruction body is empty")
            )
        extra = metadata.get("metadata")
        version = (
            str(extra.get("version", "0.0.0+imported"))
            if isinstance(extra, dict)
            else "0.0.0+imported"
        )
        discovered.append(
            DiscoveredSkill(
                root=root,
                instruction_file=instruction_file,
                source_files=source_files,
                skill_id=str(metadata.get("name", root.name)),
                version=version,
                name=str(metadata.get("name", root.name)),
                description=str(metadata.get("description", "")),
                instructions=body.strip(),
                obligations=tuple(obligations),
            )
        )
    return tuple(discovered)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    cursor = 1 if text.startswith("\ufeff") else 0
    if not text.startswith("---\n", cursor):
        return {}, text
    end = text.find("\n---", cursor + 4)
    if end < 0:
        return {}, text
    payload = yaml.safe_load(text[cursor + 4 : end]) or {}
    if not isinstance(payload, dict):
        raise ValueError("skill frontmatter must be a mapping")
    return {str(key): value for key, value in payload.items()}, text[end + 4 :].lstrip(
        "\r\n"
    )


def load_configuration(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            payload = json.loads(text)
        elif path.suffix.lower() == ".toml":
            payload = tomllib.loads(text)
        else:
            payload = yaml.safe_load(text)
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        tomllib.TOMLDecodeError,
        yaml.YAMLError,
    ):
        return None
    return payload if isinstance(payload, dict) else None


def _credential_file(path: Path) -> bool:
    return path.name.lower() in {
        ".credentials",
        "credentials",
        "credentials.json",
        "secrets.json",
    } or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}


__all__ = [
    "BuildObligation",
    "DiscoveredSkill",
    "discover_skills",
    "load_configuration",
    "parse_frontmatter",
]
