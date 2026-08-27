# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from pathlib import Path

from prism.language import check, compile, elaborate, parse_source
from prism.sdk.workspace import WorkspaceModuleLoader

ROOT = Path(__file__).resolve().parents[2]

SOURCE = """from prism.reasoning.methods.abductive import AbductionInput, Abductive

def NaturalCandidate(candidate: Nat) -> Prop:
    return candidate == candidate

def EqualParts(total: Nat, candidate: Nat) -> Prop:
    return candidate + candidate == total

def CompletesSum(total: Nat, candidate: Nat, known_part: Nat) -> Prop:
    return known_part + candidate == total

def MissingAddendProtocol(
    total: Nat,
    candidate: Nat,
    known_part: Nat,
) -> Prop:
    return NaturalCandidate(candidate) and EqualParts(total, candidate) and CompletesSum(total, candidate, known_part)

relation SupportMissingAddend(
    source: AbductionInput[Nat, Nat],
    target: Nat,
) |~ MissingAddendProtocol(source.background, target, source.observation)

relation EstablishMissingAddend(
    source: AbductionInput[Nat, Nat],
    target: Nat,
) |- MissingAddendProtocol(source.background, target, source.observation)

reasoning MaterialCompleteEqualSum(
    source: AbductionInput[Nat, Nat],
) -> Nat:
    [missing: Abductive[Nat, Nat, Nat](source)] by SupportMissingAddend
    return missing

reasoning StrictCompleteEqualSum(
    source: AbductionInput[Nat, Nat],
) -> Nat:
    [missing: Abductive[Nat, Nat, Nat](source)] by EstablishMissingAddend
    return missing
"""


def _check():
    loader = WorkspaceModuleLoader(project_root=ROOT, entry_points=False)
    return check(
        parse_source(SOURCE, path="missing_addend_protocol.prism"),
        module_loader=loader,
    )


def test_one_abductive_method_accepts_material_and_strict_relations() -> None:
    checked = _check()
    material = checked.reasoning_methods["MaterialCompleteEqualSum"]["missing"]
    strict = checked.reasoning_methods["StrictCompleteEqualSum"]["missing"]

    assert material.render() == "(source: AbductionInput[Nat, Nat]) -> Nat"
    assert strict == material
    assert checked.callable_contracts["SupportMissingAddend"].result.render() == (
        "Supported[MissingAddendProtocol(source.background, target, "
        "source.observation)]"
    )
    assert checked.callable_contracts["EstablishMissingAddend"].result.render() == (
        "Proof[MissingAddendProtocol(source.background, target, source.observation)]"
    )


def test_relation_based_abductive_reasoning_compiles() -> None:
    executable = compile(elaborate(_check()))

    assert executable.entry_callable is None
    assert "prism.reasoning.methods.abductive" in executable.module_hashes
