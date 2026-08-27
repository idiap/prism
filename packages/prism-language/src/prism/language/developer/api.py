# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Stable developer API for parsing, checking, elaborating, and compiling Prism."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from prism.language.core import Binding as CoreBinding
from prism.language.core import (
    CallableContract,
    CoreType,
    ModuleLoader,
    RecordContract,
    TypedModule,
)
from prism.language.core import Parameter as CoreParameter
from prism.language.kernel import CheckedModule
from prism.language.kernel import Term as KernelTerm
from prism.language.verification import ProofGoal

from .compilation import compile as compile
from .syntax.ast import Program
from .syntax.parser import parse_source as parse_source
from .type_syntax import parse_type


@dataclass(frozen=True, slots=True)
class CheckedProgram:
    program: Program
    globals: Mapping[str, CoreBinding]
    callable_contracts: Mapping[str, CallableContract]
    record_contracts: Mapping[str, RecordContract]
    aliases: Mapping[str, CoreType]
    type_parameters: Mapping[str, tuple[str, ...]]
    variants: Mapping[str, tuple[str, ...]]
    reasoning_outputs: Mapping[str, Mapping[str, CoreType]]
    reasoning_methods: Mapping[str, Mapping[str, CoreType]]
    callable_origins: Mapping[str, str | None]
    expression_types: Mapping[int, CoreType]
    proof_goals: tuple[ProofGoal, ...]
    module_hashes: Mapping[str, str]
    checked_module: CheckedModule
    expression_terms: Mapping[int, KernelTerm]


def check(
    program: Program,
    module_loader: ModuleLoader | None = None,
    *,
    modules: ModuleLoader | None = None,
) -> CheckedProgram:
    if not isinstance(program, Program):
        raise TypeError("check expects a canonical Program")
    if module_loader is not None and modules is not None:
        raise TypeError("pass either module_loader or modules, not both")
    from .checking.declarations import _Checker

    return _Checker(program, module_loader or modules).run()


def elaborate(program: CheckedProgram) -> TypedModule:
    if not isinstance(program, CheckedProgram):
        raise TypeError("elaborate expects a CheckedProgram")
    return TypedModule(
        path=program.program.path,
        source=program.program.source,
        declarations=program.program.declarations,
        globals=program.globals,
        callable_contracts=program.callable_contracts,
        record_contracts=program.record_contracts,
        expression_types=program.expression_types,
        proof_goals=program.proof_goals,
        module_hashes=program.module_hashes,
        aliases=program.aliases,
        type_parameters=program.type_parameters,
        variants=program.variants,
        reasoning_outputs=program.reasoning_outputs,
        reasoning_methods=program.reasoning_methods,
        callable_origins=program.callable_origins,
        checked_module=program.checked_module,
        expression_terms=program.expression_terms,
    )


def _builtin_callable_contracts() -> dict[str, CallableContract]:
    """Return the source-visible function contracts for runtime intrinsics.

    Runtime execution remains intrinsic, but these names are ordinary typed
    callable values to the frontend.  Keeping the generic parameters on the
    contracts also lets language tooling instantiate their result types rather
    than treating each name as ``Any``.
    """

    specs = {
        "Err": (
            ("E",),
            (("error", "E"),),
            "Err[E]",
            (),
        ),
        "Ok": (
            ("A",),
            (("value", "A"),),
            "Ok[A]",
            (),
        ),
        "combine_evidence": (
            ("A", "B"),
            (
                ("evidence", "Evidence[A]"),
                ("value", "B"),
                ("transformation", "String"),
            ),
            "Evidence[B]",
            (),
        ),
        "compute": (
            ("A",),
            (
                ("value", "A"),
                ("procedure", "String"),
            ),
            "Computed[A]",
            (),
        ),
        "connect": (
            (),
            (("identifier", "String"),),
            "Connection[Any]",
            (),
        ),
        "data_source": (
            (),
            (("identifier", "String"),),
            "Source[Any]",
            (),
        ),
        "hooks_artifact": (
            ("P",),
            (("configuration", "String"),),
            "Hooks[P]",
            (),
        ),
        "skill_artifact": (
            ("T",),
            (
                ("skill_id", "String"),
                ("version", "String"),
                ("name", "String"),
                ("description", "String"),
                ("instructions", "String"),
                ("resources", "String"),
            ),
            "Skill[T]",
            (),
        ),
        "embed": (
            (),
            (("path", "String"),),
            "Resource[Any]",
            (),
        ),
        "generate": (
            ("A",),
            (
                ("request", "Request"),
                ("model", "Model"),
                ("model_access", "ModelGenerate"),
            ),
            "Result[Generated[A], ModelFailure]",
            ("AI.Generate",),
        ),
        "graph_source": (
            (),
            (("identifier", "String"),),
            "GraphSource[Any]",
            (),
        ),
        "inline_resource": (
            (),
            (
                ("logical_path", "String"),
                ("base64_content", "String"),
                ("content_hash", "String"),
            ),
            "Resource[Bytes]",
            (),
        ),
        "length": (
            ("A",),
            (("values", "List[A]"),),
            "Int",
            (),
        ),
        "elaborate_proof": (
            ("P",),
            (("source", "String"),),
            "Result[CoreTerm[P], ProofError]",
            (),
        ),
        "kernel.check": (
            ("P",),
            (("term", "CoreTerm[P]"),),
            "Result[Proof[P], ProofError]",
            (),
        ),
        "map_evidence": (
            ("A", "B"),
            (
                ("evidence", "Evidence[A]"),
                ("value", "B"),
                ("transformation", "String"),
            ),
            "Evidence[B]",
            (),
        ),
        "material_policy": (
            (),
            (
                ("identifier", "String"),
                ("require", "List[Bool]"),
            ),
            "Any",
            (),
        ),
        "refinement_policy": (
            (),
            (("max_attempts", "Nat"),),
            "RefinementPolicy",
            (),
        ),
        "observe": (
            ("A",),
            (
                ("value", "A"),
                ("source", "String"),
                ("method", "String"),
            ),
            "Evidence[A]",
            (),
        ),
        "claim": (
            (),
            (("text", "String"),),
            "Prop",
            (),
        ),
        "query": (
            ("A",),
            (
                ("source", "Source[A]"),
                ("query", "Query"),
                ("data_access", "DataRead"),
                ("clock", "ClockRead"),
            ),
            "Result[Evidence[A], SourceError]",
            ("Data.Read", "Clock.Read"),
        ),
        "resource_evidence": (
            ("A",),
            (
                ("resource", "Resource[A]"),
                ("file_access", "FileRead"),
                ("clock", "ClockRead"),
            ),
            "Result[Evidence[A], SourceError]",
            ("File.Read", "Clock.Read"),
        ),
        "python_call": (
            ("A",),
            (
                ("operation", "String"),
                ("input", "Any"),
                ("permission", "PythonCall"),
            ),
            "Result[A, PythonError]",
            ("Python.Call",),
        ),
        "tool_call": (
            ("A",),
            (
                ("operation", "String"),
                ("input", "Any"),
                ("connection", "Connection[Any]"),
                ("permission", "ToolCall"),
            ),
            "Result[A, ToolError]",
            ("Tool.Call",),
        ),
        "validate": (
            ("A", "P"),
            (
                ("value", "A"),
                ("validator", "String"),
                ("require", "List[Bool]"),
            ),
            "Result[Validated[value: A, P], ValidationError]",
            (),
        ),
        "verify": (
            ("A", "P"),
            (
                ("value", "A"),
                ("proof", "Proof[P]"),
            ),
            "Verified[A, P]",
            (),
        ),
    }
    return {
        name: CallableContract(
            name=name,
            parameters=tuple(
                CoreParameter(parameter_name, parse_type(parameter_type))
                for parameter_name, parameter_type in parameters
            ),
            result=parse_type(result),
            effects=effects,
            kind="intrinsic",
            type_parameters=type_parameters,
        )
        for name, (type_parameters, parameters, result, effects) in specs.items()
    }


def _builtin_bindings(
    callable_contracts: Mapping[str, CallableContract] | None = None,
) -> dict[str, CoreBinding]:
    names = {
        "Err",
        "False",
        "Ok",
        "True",
        "elaborate_proof",
        "combine_evidence",
        "connect",
        "data_source",
        "embed",
        "generate",
        "graph_source",
        "hooks_artifact",
        "inline_resource",
        "length",
        "kernel",
        "map_evidence",
        "material_policy",
        "refinement_policy",
        "observe",
        "claim",
        "compute",
        "query",
        "python_call",
        "resource_evidence",
        "skill_artifact",
        "tool_call",
        "validate",
        "verify",
    }
    contracts = callable_contracts or _builtin_callable_contracts()
    return {
        name: CoreBinding(
            name,
            contracts[name].type if name in contracts else CoreType("Any"),
            contracts.get(name),
        )
        for name in names
    }
