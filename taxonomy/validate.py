#!/usr/bin/env python3
"""Validate taxonomy identifiers and exact catalog occurrence coverage."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

MAPPED_FACETS = {
    "primary_family": "primary_family",
    "operational_roles": "operational_roles",
    "reasoning_archetypes": "reasoning_archetypes",
    "discourse_functions": "discourse_functions",
    "substrate": "substrate",
    "computational_character": "computational_character",
}
REQUIRED_COLUMNS = {
    "project_id",
    "workflow_id",
    "occurrence_id",
    "method",
    "source_line",
    "input_type",
    "output_type",
    "primary_family",
    "operational_roles",
    "reasoning_archetypes",
    "discourse_functions",
    "substrate",
    "computational_character",
    "confidence",
    "rationale",
}
IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
ALLOWED_CARDINALITY = {"exactly_one", "one_or_more", "zero_or_one", "zero_or_more"}
ALLOWED_MAPPING_STATUS = {
    "populated_in_component_mapping",
    "legacy_populated_in_component_mapping",
    "not_yet_populated_in_component_mapping",
}
ALLOWED_ANNOTATION_LEVEL = {
    "occurrence",
    "occurrence_output",
    "occurrence_or_object",
    "object",
    "object_in_occurrence",
    "workflow",
}


def split_values(value: str) -> list[str]:
    return [item for item in value.split("|") if item]


def catalog_occurrences(
    bundle: dict[str, Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    occurrences: dict[tuple[str, str, str], dict[str, Any]] = {}
    for project in bundle.get("projects", []):
        for workflow in project.get("workflows", []):
            for node in workflow.get("graph", {}).get("nodes", []):
                if node.get("kind") != "occurrence":
                    continue
                key = (
                    str(project.get("id")),
                    str(workflow.get("id")),
                    str(node.get("id")),
                )
                if key in occurrences:
                    raise ValueError(f"duplicate catalog occurrence: {'/'.join(key)}")
                occurrences[key] = {
                    "method": str(node.get("method") or ""),
                    "source_line": str(node.get("source_span", {}).get("line") or ""),
                    "input_type": str(node.get("input_type") or ""),
                    "output_type": str(node.get("output_type") or ""),
                }
    return occurrences


def validate(
    bundle_path: Path,
    taxonomy_path: Path,
    mapping_path: Path,
) -> list[str]:
    errors: list[str] = []
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    expected = catalog_occurrences(bundle)

    with mapping_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or [])
        rows = list(reader)

    missing_columns = sorted(REQUIRED_COLUMNS - columns)
    if missing_columns:
        errors.append(f"mapping lacks required columns: {', '.join(missing_columns)}")
        return errors

    keys = [
        (row["project_id"], row["workflow_id"], row["occurrence_id"]) for row in rows
    ]
    _validate_occurrence_keys(keys, expected, errors)

    errors.extend(validate_schema(taxonomy))
    facets = taxonomy.get("facets", {})
    allowed_confidence = set(
        taxonomy.get("annotation_policy", {}).get("confidence", {})
    )
    for row, key in zip(rows, keys, strict=True):
        locator = "/".join(key)
        source = expected.get(key)
        if source:
            for field in ("method", "source_line", "input_type", "output_type"):
                if row[field] != source[field]:
                    errors.append(
                        f"{locator}: {field} differs from catalog "
                        f"({row[field]!r} != {source[field]!r})"
                    )

        if "|" in row["primary_family"]:
            errors.append(f"{locator}: primary_family must contain exactly one value")
        if not row["primary_family"]:
            errors.append(f"{locator}: primary_family is empty")

        _validate_row_facets(row, facets, locator, errors)
        _validate_row_intent(row, locator, allowed_confidence, errors)

    _validate_coverage(facets, rows, errors)

    return errors


def validate_schema(taxonomy: dict[str, Any]) -> list[str]:
    """Validate maintained identifiers independently of historical coverage."""
    errors: list[str] = []
    facets = taxonomy.get("facets", {})
    _validate_schema_header(taxonomy, errors)
    for facet_name, facet in facets.items():
        _validate_facet(facet_name, facet, errors)
        taxa = facet.get("taxa", {})
        _validate_taxa(taxa, facets, facet_name, errors)
        _validate_parent_cycles(taxa, facet_name, errors)
        for replacement_facet in facet.get("replaced_by", []):
            if replacement_facet not in facets:
                errors.append(
                    f"taxonomy {facet_name}: unknown replacement facet "
                    f"{replacement_facet!r}"
                )

    realization = facets.get("reasoning_realization", {})
    realization_axes = set(realization.get("profile_axes", []))
    for taxon_id, taxon in realization.get("taxa", {}).items():
        if taxon.get("axis") not in realization_axes:
            errors.append(
                f"taxonomy reasoning_realization/{taxon_id}: invalid or missing axis"
            )

    return errors


def _validate_schema_header(taxonomy, errors):
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(taxonomy.get("schema_version") or "")):
        errors.append("taxonomy schema_version must use semantic version form")
    if (
        taxonomy.get("identifier_policy", {}).get("canonical_form")
        != "lower_snake_case"
    ):
        errors.append("taxonomy identifier_policy must declare lower_snake_case")
    if set(taxonomy.get("taxon_status_policy", {})) != {
        "active",
        "provisional",
        "deprecated",
    }:
        errors.append("taxonomy taxon_status_policy must define all three statuses")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", str(taxonomy.get("taxonomy_id") or "")):
        errors.append("taxonomy requires a canonical taxonomy_id")
    if not {"primary_family", "reasoning_archetypes"} <= set(
        taxonomy.get("facets", {})
    ):
        errors.append(
            "taxonomy requires primary_family and reasoning_archetypes facets"
        )


def _validate_parent(taxon, taxa, facet_name, taxon_id, errors):
    parent = taxon.get("parent")
    if parent and parent not in taxa:
        errors.append(f"taxonomy {facet_name}/{taxon_id}: unknown parent {parent!r}")
    elif (
        parent
        and taxa[parent].get("status") == "deprecated"
        and taxon.get("status") != "deprecated"
    ):
        errors.append(
            f"taxonomy {facet_name}/{taxon_id}: non-deprecated taxon "
            f"has deprecated parent {parent!r}"
        )


def _validate_replacements(taxon, facets, facet_name, taxon_id, errors):
    for replacement in taxon.get("replacement", []):
        replacement_facet, separator, replacement_taxon = str(replacement).partition(
            "."
        )
        if (
            not separator
            or replacement_facet not in facets
            or replacement_taxon
            not in facets.get(replacement_facet, {}).get("taxa", {})
        ):
            errors.append(
                f"taxonomy {facet_name}/{taxon_id}: unknown replacement {replacement!r}"
            )


def _validate_parent_cycles(taxa, facet_name, errors):
    for taxon_id in taxa:
        ancestors: set[str] = set()
        current = taxon_id
        while current in taxa and taxa[current].get("parent"):
            current = str(taxa[current]["parent"])
            if current in ancestors or current == taxon_id:
                errors.append(
                    f"taxonomy {facet_name}/{taxon_id}: parent cycle detected"
                )
                break
            ancestors.add(current)


def _validate_taxa(taxa, facets, facet_name, errors):
    for taxon_id, taxon in taxa.items():
        if not IDENTIFIER.fullmatch(taxon_id):
            errors.append(
                f"taxonomy {facet_name}: non-canonical taxon identifier {taxon_id!r}"
            )
        if taxon.get("status") not in {"active", "provisional", "deprecated"}:
            errors.append(
                f"taxonomy {facet_name}/{taxon_id}: invalid or missing status"
            )
        if not str(taxon.get("definition") or "").strip():
            errors.append(f"taxonomy {facet_name}/{taxon_id}: definition is empty")
        _validate_parent(taxon, taxa, facet_name, taxon_id, errors)
        for boundary in ("include_when", "exclude_when"):
            if not str(taxon.get(boundary) or "").strip():
                errors.append(f"taxonomy {facet_name}/{taxon_id}: lacks {boundary}")
        if taxon.get("status") == "deprecated" and not taxon.get("replacement"):
            errors.append(
                f"taxonomy {facet_name}/{taxon_id}: deprecated taxon lacks replacement"
            )
        _validate_replacements(taxon, facets, facet_name, taxon_id, errors)


def _validate_facet(facet_name, facet, errors):
    if not IDENTIFIER.fullmatch(facet_name):
        errors.append(f"taxonomy facet has non-canonical identifier {facet_name!r}")
    if facet.get("cardinality") not in ALLOWED_CARDINALITY:
        errors.append(f"taxonomy {facet_name}: invalid or missing cardinality")
    if facet.get("mapping_status") not in ALLOWED_MAPPING_STATUS:
        errors.append(f"taxonomy {facet_name}: invalid or missing mapping_status")
    if facet.get("annotation_level") not in ALLOWED_ANNOTATION_LEVEL:
        errors.append(f"taxonomy {facet_name}: invalid or missing annotation_level")
    if not str(facet.get("definition") or "").strip():
        errors.append(f"taxonomy {facet_name}: definition is empty")

    is_mapped = facet_name in MAPPED_FACETS.values()
    declares_mapping = facet.get("mapping_status") in {
        "populated_in_component_mapping",
        "legacy_populated_in_component_mapping",
    }
    if is_mapped != declares_mapping:
        errors.append(
            f"taxonomy {facet_name}: mapping_status disagrees with component mapping schema"
        )


def _validate_coverage(facets, rows, errors):
    for facet_name, facet in facets.items():
        taxa = facet.get("taxa", {})
        is_mapped = facet_name in MAPPED_FACETS.values()
        if is_mapped:
            column = next(
                column
                for column, mapped_facet in MAPPED_FACETS.items()
                if mapped_facet == facet_name
            )
            used = Counter(value for row in rows for value in split_values(row[column]))
            for taxon_id, taxon in taxa.items():
                if taxon.get("status") == "active" and not used[taxon_id]:
                    errors.append(
                        f"taxonomy {facet_name}/{taxon_id}: active taxon has no maintained mapping"
                    )


def _validate_row_facets(row, facets, locator, errors):
    for column, facet_name in MAPPED_FACETS.items():
        taxon_table = facets.get(facet_name, {}).get("taxa", {})
        values = split_values(row[column])
        if len(values) != len(set(values)):
            errors.append(f"{locator}: {column} contains duplicate values")
        for value in values:
            if value not in taxon_table:
                errors.append(f"{locator}: unknown {facet_name} taxon {value!r}")
            elif taxon_table[value].get("status") != "active":
                errors.append(f"{locator}: {facet_name} taxon {value!r} is not active")

        cardinality = facets.get(facet_name, {}).get("cardinality")
        if cardinality == "exactly_one" and len(values) != 1:
            errors.append(f"{locator}: {column} requires exactly one value")
        elif cardinality == "one_or_more" and not values:
            errors.append(f"{locator}: {column} requires at least one value")
        elif cardinality == "zero_or_one" and len(values) > 1:
            errors.append(f"{locator}: {column} permits at most one value")


def _validate_row_intent(row, locator, allowed_confidence, errors):
    reasoning = split_values(row["reasoning_archetypes"])
    if row["primary_family"] == "core_reasoning" and not reasoning:
        errors.append(f"{locator}: core_reasoning requires a reasoning archetype")
    if reasoning and row["primary_family"] not in {
        "core_reasoning",
        "evaluation_and_judgment",
    }:
        errors.append(
            f"{locator}: reasoning archetypes require a reasoning or evaluation family"
        )

    if row["confidence"] not in allowed_confidence:
        errors.append(f"{locator}: unknown confidence {row['confidence']!r}")
    if not row["rationale"].strip():
        errors.append(f"{locator}: rationale is empty")


def _validate_occurrence_keys(keys, expected, errors):
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    for key in duplicates:
        errors.append(f"duplicate mapping row: {'/'.join(key)}")

    actual = set(keys)
    for key in sorted(set(expected) - actual):
        errors.append(f"unmapped catalog occurrence: {'/'.join(key)}")
    for key in sorted(actual - set(expected)):
        errors.append(f"mapping row has no catalog occurrence: {'/'.join(key)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=Path("catalog/graphs.json"))
    parser.add_argument("--taxonomy", type=Path, default=Path("taxonomy/taxonomy.json"))
    parser.add_argument(
        "--mapping", type=Path, default=Path("taxonomy/component-mapping.csv")
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="validate taxonomy metadata without historical catalog or mapping files",
    )
    args = parser.parse_args()
    try:
        if args.schema_only:
            errors = validate_schema(
                json.loads(args.taxonomy.read_text(encoding="utf-8"))
            )
        else:
            if not args.bundle.is_file():
                parser.error(
                    f"corpus audit requires missing catalog input: {args.bundle}"
                )
            errors = validate(args.bundle, args.taxonomy, args.mapping)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.schema_only:
        print(
            "OK: taxonomy schema and identifiers are valid; corpus coverage was not audited"
        )
        return 0
    with args.mapping.open(encoding="utf-8", newline="") as stream:
        count = sum(1 for _ in csv.DictReader(stream))
    print(f"OK: {count} catalog occurrences have valid, unique taxonomy mappings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
