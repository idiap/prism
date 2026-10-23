# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
# SPDX-License-Identifier: MIT

"""Observed claim and assurance states, independent of execution completion."""

from prism.language.core import DependentPair, ValidatedValue
from prism.language.evidence import Assessment, Supported
from prism.language.kernel import CheckedTerm
from prism.runtime.results import ObservedValue

from .provenance import _children


def observed_values(tracker, value, reference, path=()):
    ref = tracker.values.get(reference)
    producer = tracker.activities[ref.activity].kind if ref else "external_unknown"
    assurance, disposition, assumptions = _claim_state(value)
    claim, certificate = _claim_details(value)
    root = ObservedValue(
        path,
        reference,
        producer,
        assurance,
        disposition,
        assumptions,
        claim,
        certificate,
    )
    return (
        root,
        *(
            observed
            for suffix, child, child_ref in _observed_children(value, ref)
            for observed in observed_values(tracker, child, child_ref, (*path, *suffix))
        ),
    )


def _observed_children(value, ref):
    if isinstance(value, dict):
        entries = ref.entries if ref else ((None, None),) * len(value)
        for index, ((key, item), (key_ref, value_ref)) in enumerate(
            zip(value.items(), entries, strict=True)
        ):
            yield ("keys", str(index)), key, key_ref
            yield ("values", str(index)), item, value_ref
        return
    children = dict(ref.children) if ref else {}
    for name, child in _children(value):
        yield (name,), child, children.get(name)


def _claim_state(value):
    if isinstance(value, Supported):
        return "supported", value.assessment.disposition, ()
    if isinstance(value, Assessment):
        return "unchecked", value.disposition, ()
    if isinstance(value, ValidatedValue):
        return (
            "validated" if value.result else "unchecked",
            "accepted" if value.result else "rejected",
            (),
        )
    if isinstance(value, CheckedTerm | DependentPair):
        return "proved", "accepted", tuple(sorted(value.axioms))
    return "unchecked", "not_applicable", ()


def _claim_details(value):
    if isinstance(value, Supported):
        value = value.assessment
    if isinstance(value, Assessment):
        return value.claim, {
            "policy_identity": value.policy_identity,
            "policy_hash": value.policy_hash,
            "evidence_reference": value.evidence_reference,
        }
    if isinstance(value, ValidatedValue):
        return value.claim, {
            "validator": value.validator,
            "validator_hash": value.validator_hash,
        }
    if isinstance(value, DependentPair):
        value = value.proof
    if isinstance(value, CheckedTerm):
        return value.type, {
            "proposition_hash": value.type_hash,
            "proof_hash": value.term_hash,
            "environment_hash": value.environment_hash,
        }
    return None, None
