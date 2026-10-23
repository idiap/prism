# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

import hashlib

import pytest
from prism.language import check, compile, elaborate, parse_source
from prism.language.core import CoreType, InMemoryModuleLoader
from prism.language.developer import PrismTypeError
from prism.runtime import FakeEffectHandler, run


@pytest.mark.parametrize(
    ("imports", "expression"),
    [
        ("from values import exported as result", "result"),
        ("from values import answer as result", "result()"),
        ("import values as sample", "sample.exported"),
    ],
)
def test_imports_preserve_private_value_and_callable_dependencies(
    imports: str, expression: str
) -> None:
    source = """prefix = "private"
def helper() -> String:
    return prefix
def answer() -> String:
    return helper()
exported = answer()
"""
    checked = check(
        parse_source(f"{imports}\ndef main() -> String:\n    return {expression}\n"),
        module_loader=InMemoryModuleLoader({"values": source}),
    )

    output = run(compile(elaborate(checked)), handler=FakeEffectHandler())

    assert output.result == "private"
    assert (
        checked.module_hashes["values"] == hashlib.sha256(source.encode()).hexdigest()
    )


@pytest.mark.parametrize(
    "imports",
    ["from recursive import first", "from recursive import first, second"],
)
def test_imports_bind_mutually_recursive_callables_before_dependencies(
    imports: str,
) -> None:
    source = """def first(stop: Bool) -> Bool:
    return True if stop else second(True)
def second(stop: Bool) -> Bool:
    return False if stop else first(True)
"""
    checked = check(
        parse_source(f"{imports}\ndef main() -> Bool:\n    return first(False)\n"),
        module_loader=InMemoryModuleLoader({"recursive": source}),
    )

    output = run(compile(elaborate(checked)), handler=FakeEffectHandler())

    assert output.result is False
    assert checked.callable_origins["second"] == "memory:recursive"


@pytest.mark.parametrize(
    ("imports", "record", "alias", "variant", "constructor"),
    [
        (
            "from types import Box as Crate, Label as Text, Choice as Selection",
            "Crate",
            "Text",
            "Selection",
            "Selected",
        ),
        (
            "import types as sample",
            "sample.Box",
            "sample.Label",
            "sample.Choice",
            "sample.Selected",
        ),
    ],
)
def test_imports_preserve_generic_types_and_variant_constructors(
    imports: str, record: str, alias: str, variant: str, constructor: str
) -> None:
    checked = check(
        parse_source(imports + "\n"),
        module_loader=InMemoryModuleLoader(
            {
                "types": """type Box[Value]:
    value: Value
type Label = String
type Choice:
    | Selected(value: String)
    | Skipped
"""
            }
        ),
    )

    assert checked.type_parameters[record] == ("Value",)
    assert checked.aliases[alias] == CoreType("String")
    assert checked.variants[variant] == ("Selected", "Skipped")
    assert checked.record_contracts[constructor].fields[0].type == CoreType("String")
    assert constructor in checked.globals


@pytest.mark.parametrize(
    ("source", "modules", "code"),
    [
        ("from missing import value\n", None, "type-import-loader"),
        ("from missing import value\n", {}, "type-import-module"),
        ("from empty import value\n", {"empty": ""}, "type-import-export"),
        (
            "import cycle as c\n",
            {"cycle": "import cycle as c\n"},
            "type-import-cycle",
        ),
        ("type Name = String\ntype Name = Int\n", None, "type-duplicate"),
        (
            "type Pair:\n    value: String\n    value: Int\n",
            None,
            "type-record-duplicate-field",
        ),
        (
            "type Choice:\n    | Selected(String)\n",
            None,
            "type-variant-field",
        ),
        (
            "relation Relates(source: String) -> String\n",
            None,
            "type-relation-endpoints",
        ),
    ],
)
def test_declaration_diagnostics_are_preserved(
    source: str, modules: dict[str, str] | None, code: str
) -> None:
    loader = None if modules is None else InMemoryModuleLoader(modules)

    with pytest.raises(PrismTypeError) as error:
        check(parse_source(source), module_loader=loader)

    assert error.value.diagnostic.code == code


def test_kernel_admission_keeps_pure_definitions_and_skips_runtime_bindings() -> None:
    checked = check(
        parse_source("""seed: Nat = 2
label: String = "runtime"
def identity(value: Nat) -> Nat:
    return value
def echo(value: String) -> String:
    return value
""")
    )

    assert checked.checked_module is not None
    names = {item.name for item in checked.checked_module.declarations}
    assert {"seed", "identity"} <= names
    assert names.isdisjoint({"label", "echo"})
    assert "label" in checked.globals
    assert "echo" in checked.callable_contracts


def test_proposition_identity_survives_import_renaming_and_distinguishes_modules() -> (
    None
):
    modules = InMemoryModuleLoader(
        {
            "left": "def Accepted(value: Int) -> Prop\n",
            "right": "def Accepted(value: Int) -> Prop\n",
        }
    )
    check(
        parse_source("""import left as first
from left import Accepted as Renamed
def keep(proof: Proof[first.Accepted(7)]) -> Proof[Renamed(7)]:
    return proof
"""),
        module_loader=modules,
    )
    with pytest.raises(PrismTypeError):
        check(
            parse_source("""import left as first
import right as second
def wrong(proof: Proof[first.Accepted(7)]) -> Proof[second.Accepted(7)]:
    return proof
"""),
            module_loader=modules,
        )


def test_checked_and_elaborated_propositions_keep_structural_binding_identities() -> (
    None
):
    from prism.language import elaborate

    checked = check(
        parse_source("""def Accepted(value: Int) -> Prop
value = 7
def local(value: Int, proof: Proof[Accepted(value)]) -> Proof[Accepted(value)]:
    return proof
""")
    )
    claim = checked.callable_contracts["local"].result.arguments[0]
    assert claim.proposition is not None
    assert claim.name == "Proposition"
    callee, argument = claim.proposition.children
    assert callee.symbol == "Main::Accepted"
    assert argument.symbol != checked.globals["value"].identity
    assert argument.symbol == checked.callable_contracts["local"].parameters[0].identity
    assert elaborate(checked).callable_contracts["local"].result.arguments[0] == claim


def test_imported_value_aliases_preserve_their_original_index() -> None:
    modules = InMemoryModuleLoader(
        {
            "values": """value = 7
alias = value
def Accepted(value: Int) -> Prop
"""
        }
    )
    check(
        parse_source("""import values as sample
def keep(proof: Proof[sample.Accepted(sample.alias)]) -> Proof[sample.Accepted(sample.value)]:
    return proof
"""),
        module_loader=modules,
    )


@pytest.mark.parametrize(
    "private_type",
    [
        "type Hidden:\n    value: String\n",
        "type Hidden = String\n",
        "type Hidden:\n    | Secret(value: String)\n",
    ],
)
def test_namespace_imports_only_publish_bound_types(private_type: str) -> None:
    modules = InMemoryModuleLoader(
        {
            "domain": "type Used:\n    value: Int\n" + private_type,
            "bridge": "from domain import Used as Public\n",
            "facade": "from bridge import Public\n",
        }
    )
    checked = check(
        parse_source("""import facade as sample
def main() -> Int:
    value = sample.Public(value = 7)
    return value.value
"""),
        module_loader=modules,
    )

    assert checked.globals["sample.Public"].identity == "memory:domain::Used"
    assert "sample.Hidden" not in checked.globals
    assert "sample.Hidden" not in checked.aliases
    assert "sample.Secret" not in checked.globals
    assert "sample.Used" not in checked.globals
    output = run(compile(elaborate(checked)), handler=FakeEffectHandler())
    assert output.result == 7

    for imported in ("Hidden", "Used"):
        with pytest.raises(PrismTypeError) as error:
            check(
                parse_source(f"from facade import {imported}\n"),
                module_loader=modules,
            )
        assert error.value.diagnostic.code == "type-import-export"


def test_namespace_keeps_private_record_dependencies_for_returned_values() -> None:
    modules = InMemoryModuleLoader(
        {
            "domain": """type Private:
    value: Int
def make() -> Private:
    return Private(value = 9)
""",
            "bridge": "from domain import make\n",
        }
    )
    checked = check(
        parse_source("""import bridge as sample
def main() -> Int:
    value = sample.make()
    return value.value
"""),
        module_loader=modules,
    )

    assert "Private" in checked.record_contracts
    assert "sample.Private" not in checked.globals
    assert checked.callable_contracts["main"].result == CoreType("Int")
    compile(elaborate(checked))
