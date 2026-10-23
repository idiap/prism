# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT


"""Compile diagram sequence notation into dependency sets."""

from __future__ import annotations

import re

from .models import WorkflowDiagramSpec


def dependencies(spec: WorkflowDiagramSpec) -> dict[str, set[str]]:
    """Compile the rover-style `sequence` block into dependency sets."""
    dependencies: dict[str, set[str]] = {}
    declared_nodes = set(spec.nodes)
    current_sources: list[str] = []

    for raw_line in spec.sequence.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and "]=>" in line:
            match = re.match(r"^\[(?P<sources>[^\]]+)\]=>\s*(?P<target>.+)$", line)
            if not match:
                raise ValueError(
                    f"Invalid workflow join line in `{spec.name}`: {raw_line}"
                )
            join_sources = [
                item.strip()
                for item in match.group("sources").split(",")
                if item.strip()
            ]
            target = match.group("target").strip()
            dependencies.setdefault(target, set())
            dependencies[target].update(join_sources)
            current_sources = [target]
            continue
        if "--->" in line and not line.startswith("--->"):
            segments = [
                segment.strip() for segment in line.split("--->") if segment.strip()
            ]
            current_sources = [segments[0]]
            dependencies.setdefault(segments[0], set())
            for segment in segments[1:]:
                current_sources = _register_target(
                    segment, dependencies, current_sources
                )
            continue
        if line.startswith("--->"):
            if not current_sources:
                raise ValueError(
                    f"Workflow arrow in `{spec.name}` has no current source: {raw_line}"
                )
            current_sources = _register_target(
                line.removeprefix("--->").strip(), dependencies, current_sources
            )
            continue
        current_sources = [line]
        dependencies.setdefault(line, set())

    return _complete_dependencies(spec, dependencies, declared_nodes)


def _register_target(
    target_text: str, dependencies: dict[str, set[str]], current_sources: list[str]
) -> list[str]:
    target_text = target_text.strip()
    if target_text.startswith("else=>"):
        target_text = target_text.removeprefix("else=>").strip()
    if " ? when:" in target_text:
        target_text = target_text.split(" ? when:", maxsplit=1)[0].strip()
    targets = [target_text]
    if target_text.startswith("(") and target_text.endswith(")"):
        targets = [
            item.strip() for item in target_text[1:-1].split("|") if item.strip()
        ]
    for node_id in targets:
        dependencies.setdefault(node_id, set()).update(current_sources)
    return targets


def _complete_dependencies(
    spec: WorkflowDiagramSpec,
    dependencies: dict[str, set[str]],
    declared_nodes: set[str],
) -> dict[str, set[str]]:
    dependencies.setdefault(spec.entrypoint, set())
    unknown_nodes = [
        node_id
        for node_id in dependencies
        if declared_nodes and node_id not in declared_nodes
    ]
    if unknown_nodes:
        missing = ", ".join(sorted(unknown_nodes))
        raise ValueError(
            f"Workflow diagram `{spec.name}` references undeclared node(s): {missing}"
        )
    for node_id in declared_nodes:
        dependencies.setdefault(node_id, set())
    return dependencies
