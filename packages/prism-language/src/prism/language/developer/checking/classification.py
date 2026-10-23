# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
# SPDX-License-Identifier: MIT

"""Resolve declarative method classification against injected taxonomy data."""

import json
from typing import Literal, cast

from prism.language.core.occurrences import ReasoningClassification, TaxonomyReference


def method_classification(checker, metadata) -> ReasoningClassification:
    if checker.module_loader is None:
        checker.fail(
            "method metadata requires a taxonomy module loader",
            metadata.span,
            "type-taxonomy-loader",
        )
    assert checker.module_loader is not None
    try:
        source = checker.module_loader.load_taxonomy(
            metadata.taxonomy, metadata.version
        )
        taxonomy = json.loads(source.source)
        if (source.identity, source.version) != (
            metadata.taxonomy,
            metadata.version,
        ) or (taxonomy.get("taxonomy_id"), taxonomy.get("schema_version")) != (
            metadata.taxonomy,
            metadata.version,
        ):
            raise ValueError(
                "loaded taxonomy does not match the declared identifier and version"
            )
        references = _references(taxonomy, metadata)
        _check_family(dict(metadata.facets), metadata.archetype_state)
    except (ValueError, KeyError, TypeError) as exc:
        checker.fail(str(exc), metadata.span, "type-taxonomy-metadata")
    return ReasoningClassification("classified", references, metadata.archetype_state)


def _references(taxonomy, metadata) -> tuple[TaxonomyReference, ...]:
    references = []
    for name, values in metadata.facets:
        facet = taxonomy["facets"].get(name)
        if facet is None:
            raise ValueError(f"unknown taxonomy facet `{name}`")
        if facet.get("status") == "deprecated" or facet.get("replaced_by"):
            raise ValueError(f"deprecated taxonomy facet `{name}`")
        _check_cardinality(name, values, facet["cardinality"])
        for value in values:
            taxon = facet["taxa"].get(value)
            if taxon is None:
                raise ValueError(f"unknown taxonomy reference `{name}.{value}`")
            status = taxon.get("status")
            if status not in {"active", "provisional"}:
                raise ValueError(
                    f"deprecated or invalid taxonomy reference `{name}.{value}`"
                )
            references.append(
                TaxonomyReference(
                    metadata.taxonomy,
                    metadata.version,
                    name,
                    value,
                    cast(Literal["active", "provisional"], status),
                )
            )
    return tuple(references)


def _check_cardinality(name, values, cardinality):
    if len(set(values)) != len(values):
        raise ValueError(f"duplicate taxonomy reference in `{name}`")
    invalid = {
        "exactly_one": len(values) != 1,
        "one_or_more": not values,
        "zero_or_one": len(values) > 1,
        "zero_or_more": False,
    }
    if cardinality not in invalid or invalid[cardinality]:
        raise ValueError(f"taxonomy facet `{name}` requires cardinality {cardinality}")


def _check_family(facets, archetype_state):
    family = facets.get("primary_family", ())
    if len(family) != 1:
        raise ValueError("method classification requires exactly one primary_family")
    archetypes = facets.get("reasoning_archetypes", ())
    if archetype_state == "unclassified":
        raise ValueError(
            "method classification requires reasoning_archetypes or explicit not_applicable"
        )
    if family == ("core_reasoning",) and not archetypes:
        raise ValueError("core_reasoning requires a reasoning archetype")
    if archetypes and family[0] not in {"core_reasoning", "evaluation_and_judgment"}:
        raise ValueError(
            "reasoning archetypes require a reasoning or evaluation family"
        )
