# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Evidence acquisition through typed source queries."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from prism.language.core import (
    CoreType,
    Err,
    Ok,
)
from prism.language.evidence import Evidence, Provenance
from prism.language.interop import (
    ResourceReference,
    SourceReference,
)
from prism.language.kernel import Term
from prism.runtime.results import TraceEvent

if TYPE_CHECKING:
    from .execution import _Engine


def _query_source(self: _Engine, args: tuple[Any, ...]) -> Any:
    from prism.runtime.knowledge import (
        FileSearchQuery,
        KeyLookupQuery,
        SqlQuery,
    )

    reference = args[0]
    if not isinstance(reference, SourceReference):
        return Err("query requires Source")
    query_value = str(args[1])
    if "patients" in reference.source_id:
        query = KeyLookupQuery(query_value, "PatientRecord")
    elif "formulary" in reference.source_id:
        query = SqlQuery(
            "SELECT drug_name, trigger_kind, trigger_value, severity, recommendation "
            "FROM medication_rules WHERE drug_name = :drug_name ORDER BY rule_id",
            {"drug_name": query_value},
            "MedicationRule",
            10,
        )
    else:
        query = FileSearchQuery(query_value, 10, "CarePathEdge")
    try:
        result = self.knowledge_broker.query(reference, query)
    except Exception as exc:
        return Err(str(exc))
    value = result.items[0].value if result.items else None
    observed_at = datetime.now(UTC).isoformat()
    evidence = Evidence(
        value,
        (
            Provenance(
                reference.source_id,
                query.query_kind,
                observed_at=observed_at,
                transformations=("typed source query",),
                integrity="SnapshotVerified",
                metadata={
                    "query": query_value,
                    "result_hash": result.result_hash,
                },
            ),
        ),
    )
    self.trace.append(
        TraceEvent(
            "source-query",
            reference.source_id,
            provenance="Evidence",
            metadata={
                "query": query_value,
                "result_hash": result.result_hash,
                "permissions": (args[2].type_name, args[3].type_name),
                "observed_at": observed_at,
            },
        )
    )
    self.provenance.produce(
        Ok(evidence),
        "acquired",
        "source query",
        source=reference.source_id,
        source_hash=result.result_hash,
    )
    return Ok(evidence)


def _builtin_resource_evidence(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    reference = args[0]
    if not isinstance(reference, ResourceReference):
        return Err("resource_evidence requires Resource")
    if reference.content is not None:
        value = reference.content
    else:
        if self.resource_resolver is None:
            return Err("external resource requires a resource resolver")
        try:
            value = self.resource_resolver.resolve(reference)
        except TypeError:
            value = self.resource_resolver.resolve(
                reference.locator, reference.type_name
            )
    observed_at = datetime.now(UTC).isoformat()
    evidence = Evidence(
        value,
        (
            Provenance(
                reference.locator,
                "inline resource assertion"
                if reference.content is not None
                else "local resource read",
                observed_at=observed_at,
                integrity="Supplied"
                if reference.content is not None
                else "ContentAddressed",
            ),
        ),
    )
    self.trace.append(
        TraceEvent(
            "resource-acquired",
            reference.locator,
            provenance="Evidence",
            metadata={
                "permissions": (args[1].type_name, args[2].type_name),
                "observed_at": observed_at,
            },
        )
    )
    payload = value if isinstance(value, bytes) else str(value).encode()
    self.provenance.produce(
        Ok(evidence),
        "asserted" if reference.content is not None else "acquired",
        "resource read",
        source=reference.locator,
        source_hash=sha256(payload).hexdigest(),
    )
    return Ok(evidence)


def _builtin_query(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    return self._query_source(args)
