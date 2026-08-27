# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Canonical, content-addressed Prism core-module encoding."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .diagnostics import KernelError
from .environment import (
    CheckedModule,
    Declaration,
    ModuleImport,
    RecursorRule,
    RecursorSpec,
)
from .levels import Level, LevelMax, LevelSucc, LevelVar, LevelZero, normalize_level
from .terms import (
    App,
    Const,
    ConstructorRef,
    InductiveRef,
    Lam,
    Let,
    Local,
    Pi,
    RecursorRef,
    Sort,
    Term,
)

CORE_FORMAT_VERSION = "1"
CALCULUS_VERSION = "prism-core-v1"


def level_to_data(level: Level) -> Any:
    level = normalize_level(level)
    if isinstance(level, LevelZero):
        return ["zero"]
    if isinstance(level, LevelVar):
        return ["var", level.name]
    if isinstance(level, LevelSucc):
        return ["succ", level_to_data(level.of)]
    return ["max", level_to_data(level.left), level_to_data(level.right)]


def level_from_data(data: Any) -> Level:
    if not isinstance(data, list) or not data:
        raise KernelError("malformed universe level", code="kernel-serialization-level")
    if data == ["zero"]:
        return LevelZero()
    if len(data) == 2 and data[0] == "var" and isinstance(data[1], str):
        return LevelVar(data[1])
    if len(data) == 2 and data[0] == "succ":
        return LevelSucc(level_from_data(data[1]))
    if len(data) == 3 and data[0] == "max":
        return LevelMax(level_from_data(data[1]), level_from_data(data[2]))
    raise KernelError("malformed universe level", code="kernel-serialization-level")


def term_to_data(term: Term) -> Any:
    if isinstance(term, Sort):
        return ["sort", None if term.level is None else level_to_data(term.level)]
    if isinstance(term, Local):
        return ["local", term.index]
    if isinstance(term, Const):
        return [
            "const",
            term.name,
            [level_to_data(item) for item in term.universe_arguments],
        ]
    if isinstance(term, Pi):
        return ["pi", term.name, term_to_data(term.domain), term_to_data(term.codomain)]
    if isinstance(term, Lam):
        return ["lam", term.name, term_to_data(term.domain), term_to_data(term.body)]
    if isinstance(term, App):
        return ["app", term_to_data(term.function), term_to_data(term.argument)]
    if isinstance(term, Let):
        return [
            "let",
            term.name,
            term_to_data(term.type),
            term_to_data(term.value),
            term_to_data(term.body),
        ]
    tag = {
        InductiveRef: "inductive",
        ConstructorRef: "constructor",
        RecursorRef: "recursor",
    }[type(term)]
    return [tag, term.name, [term_to_data(item) for item in term.arguments]]


def term_from_data(data: Any) -> Term:
    if not isinstance(data, list) or not data or not isinstance(data[0], str):
        raise KernelError("malformed core term", code="kernel-serialization-term")
    tag = data[0]
    try:
        if tag == "sort" and len(data) == 2:
            return Sort(None if data[1] is None else level_from_data(data[1]))
        if tag == "local" and len(data) == 2 and isinstance(data[1], int):
            return Local(data[1])
        if tag == "const" and len(data) == 3:
            return Const(str(data[1]), tuple(level_from_data(item) for item in data[2]))
        if tag == "pi" and len(data) == 4:
            return Pi(str(data[1]), term_from_data(data[2]), term_from_data(data[3]))
        if tag == "lam" and len(data) == 4:
            return Lam(str(data[1]), term_from_data(data[2]), term_from_data(data[3]))
        if tag == "app" and len(data) == 3:
            return App(term_from_data(data[1]), term_from_data(data[2]))
        if tag == "let" and len(data) == 5:
            return Let(
                str(data[1]),
                term_from_data(data[2]),
                term_from_data(data[3]),
                term_from_data(data[4]),
            )
        if tag in {"inductive", "constructor", "recursor"} and len(data) == 3:
            arguments = tuple(term_from_data(item) for item in data[2])
            cls = {
                "inductive": InductiveRef,
                "constructor": ConstructorRef,
                "recursor": RecursorRef,
            }[tag]
            return cls(str(data[1]), arguments)
    except (TypeError, ValueError, KeyError) as exc:
        raise KernelError(
            "malformed core term", code="kernel-serialization-term"
        ) from exc
    raise KernelError(
        f"unknown or malformed core term tag `{tag}`",
        code="kernel-serialization-term",
    )


def declaration_to_data(declaration: Declaration) -> dict[str, Any]:
    recursor = None
    if declaration.recursor is not None:
        recursor = {
            "scrutinee_index": declaration.recursor.scrutinee_index,
            "rules": [
                {
                    "constructor": item.constructor,
                    "constructor_arity": item.constructor_arity,
                    "method_index": item.method_index,
                    "recursive_positions": list(item.recursive_positions),
                    "field_positions": (
                        list(item.field_positions)
                        if item.field_positions is not None
                        else None
                    ),
                }
                for item in declaration.recursor.rules
            ],
        }
    return {
        "name": declaration.name,
        "kind": declaration.kind,
        "type": term_to_data(declaration.type),
        "value": (
            term_to_data(declaration.value) if declaration.value is not None else None
        ),
        "universe_parameters": list(declaration.universe_parameters),
        "transparent": declaration.transparent,
        "pure": declaration.pure,
        "total": declaration.total,
        "inductive_name": declaration.inductive_name,
        "recursor": recursor,
        "axioms": sorted(declaration.axiom_dependencies),
    }


def declaration_from_data(data: Any) -> Declaration:
    if not isinstance(data, Mapping):
        raise KernelError(
            "malformed declaration", code="kernel-serialization-declaration"
        )
    required = {"name", "kind", "type", "value"}
    if not required.issubset(data):
        raise KernelError(
            "malformed declaration", code="kernel-serialization-declaration"
        )
    recursor_data = data.get("recursor")
    recursor = None
    if recursor_data is not None:
        if not isinstance(recursor_data, Mapping):
            raise KernelError(
                "malformed recursor", code="kernel-serialization-recursor"
            )
        recursor = RecursorSpec(
            int(recursor_data["scrutinee_index"]),
            tuple(
                RecursorRule(
                    str(item["constructor"]),
                    int(item["constructor_arity"]),
                    int(item["method_index"]),
                    tuple(int(value) for value in item.get("recursive_positions", ())),
                    (
                        tuple(int(value) for value in item["field_positions"])
                        if item.get("field_positions") is not None
                        else None
                    ),
                )
                for item in recursor_data.get("rules", ())
            ),
        )
    return Declaration(
        str(data["name"]),
        term_from_data(data["type"]),
        term_from_data(data["value"]) if data["value"] is not None else None,
        data["kind"],
        tuple(str(item) for item in data.get("universe_parameters", ())),
        bool(data.get("transparent", True)),
        bool(data.get("pure", True)),
        bool(data.get("total", True)),
        data.get("inductive_name"),
        recursor,
        frozenset(str(item) for item in data.get("axioms", ())),
    )


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def term_hash(term: Term) -> str:
    return hashlib.sha256(canonical_bytes(term_to_data(term))).hexdigest()


def module_hash(
    name: str,
    imports: Sequence[ModuleImport],
    declarations: Sequence[Declaration],
) -> str:
    return hashlib.sha256(
        canonical_bytes(
            {
                "format": CORE_FORMAT_VERSION,
                "calculus": CALCULUS_VERSION,
                "name": name,
                "imports": [
                    {"name": item.name, "hash": item.content_hash}
                    for item in sorted(imports, key=lambda reference: reference.name)
                ],
                "declarations": [declaration_to_data(item) for item in declarations],
            }
        )
    ).hexdigest()


def serialize_module(module: CheckedModule) -> bytes:
    payload = {
        "format": module.core_format_version,
        "calculus": module.calculus_version,
        "name": module.name,
        "imports": [
            {"name": item.name, "hash": item.content_hash} for item in module.imports
        ],
        "declarations": [declaration_to_data(item) for item in module.declarations],
        "hash": module.content_hash,
    }
    return canonical_bytes(payload)


def deserialize_module(
    payload: bytes | str,
    imports: Mapping[str, CheckedModule] | None = None,
) -> CheckedModule:
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise KernelError(
            "invalid core module JSON", code="kernel-serialization-json"
        ) from exc
    if not isinstance(data, Mapping) or data.get("format") != CORE_FORMAT_VERSION:
        raise KernelError("unsupported core module format", code="kernel-module-format")
    if data.get("calculus") != CALCULUS_VERSION:
        raise KernelError(
            "unsupported core calculus version", code="kernel-calculus-version"
        )
    import_refs = tuple(
        ModuleImport(str(item["name"]), str(item["hash"]))
        for item in data.get("imports", ())
    )
    available = imports or {}
    checked_imports: list[CheckedModule] = []
    for reference in import_refs:
        imported = available.get(reference.name)
        if imported is None or imported.content_hash != reference.content_hash:
            raise KernelError(
                f"missing exact import `{reference.name}` at {reference.content_hash}",
                code="kernel-import-hash-mismatch",
            )
        checked_imports.append(imported)
    declarations = tuple(
        declaration_from_data(item) for item in data.get("declarations", ())
    )
    from .declarations import check_module

    checked = check_module(
        str(data.get("name", "")),
        checked_imports,
        declarations,
        expected_imports=import_refs,
    )
    if data.get("hash") != checked.content_hash:
        raise KernelError("core module hash mismatch", code="kernel-module-hash")
    return checked
