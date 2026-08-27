# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

import re
import tomllib
from pathlib import Path

from prism.language import check, parse_source
from prism.language.core import ModuleResolver
from prism.sdk.workspace import WorkspaceModuleLoader

ROOT = Path(__file__).resolve().parents[1]


def test_every_remaining_prism_source_is_canonical_and_checked() -> None:
    loader = WorkspaceModuleLoader(project_root=ROOT, entry_points=False)
    sources = sorted(
        path
        for base in (ROOT / "examples", ROOT / "libs")
        for path in base.rglob("*.prism")
    )
    removed_forms = re.compile(
        r"(?m)^\s*(?:structure|assume|derive|have|run|apply|invoke|tactic)\b"
        r"|^\s*require\b(?!\s*=)"
        r"|^\s*(?:claim|expr|equation)\s+[A-Za-z_]"
        r"|\bby\s+(?:litellm|python)\("
    )
    for path in sources:
        source = path.read_text(encoding="utf-8")
        assert removed_forms.search(source) is None, path
        check(parse_source(source, path=str(path)), module_loader=loader)

    catalog_sources = sorted((ROOT / "catalog").rglob("*.prism"))
    for path in catalog_sources:
        relative = path.relative_to(ROOT / "catalog")
        assert relative.parts[0] == "skills", path
        assert relative.name in {"manifest.prism", "package.prism"}, path
        check(parse_source(path.read_text(encoding="utf-8"), path=str(path)))
    docs_sources = sorted((ROOT / "docs/docs").rglob("*.prism"))
    docs_sources += sorted((ROOT / "docs/static").rglob("*.prism"))
    assert docs_sources == [ROOT / "docs/static/examples/quick-start/main.prism"]
    assert not list((ROOT / "libs").glob("*/skills/*.prism"))

    manifest = tomllib.loads(
        (ROOT / "libs/prism/pyproject.toml").read_text(encoding="utf-8")
    )
    data_files = manifest["tool"]["setuptools"]["data-files"]
    assert all("/skills" not in destination for destination in data_files)
    assert all(
        "skills/" not in source
        for patterns in data_files.values()
        for source in patterns
    )


def test_standard_epistemic_contracts_are_exact_library_types() -> None:
    loader = WorkspaceModuleLoader(project_root=ROOT, entry_points=False)

    def checked(relative: str):
        path = ROOT / relative
        return check(
            parse_source(path.read_text(encoding="utf-8"), path=str(path)),
            module_loader=loader,
        )

    expected_methods = {
        "deductive": ("Deductive", "Conclusion"),
        "abductive": ("Abductive", "Hypothesis"),
        "inductive": ("Inductive", "Conclusion"),
        "analogical": ("Analogical", "Conclusion"),
        "contrastive": ("Contrastive", "Conclusion"),
        "model_based": ("ModelBased", "Conclusion"),
        "refutational": ("Refutational", "Conclusion"),
        "evidential": ("Evidential", "Conclusion"),
    }
    method_modules = {
        module_name: checked(f"libs/prism/reasoning/methods/{module_name}.prism")
        for module_name in expected_methods
    }
    for module_name, (method, result_name) in expected_methods.items():
        contract = method_modules[module_name].aliases[method]
        assert contract.is_function
        assert len(contract.parameters) == 1
        assert contract.result is not None
        assert contract.result.name == result_name

    abductive = method_modules["abductive"]
    protocol = abductive.aliases["AbductionProtocol"]
    assert protocol.is_function
    assert tuple(name for name, _ in protocol.parameters) == (
        "background",
        "hypothesis",
        "observation",
    )
    assert protocol.result is not None
    assert protocol.result.name == "Prop"
    assert abductive.type_parameters["Abductive"] == (
        "Hypothesis",
        "Background",
        "Observation",
    )
    assert abductive.type_parameters["AbductionInput"] == (
        "Background",
        "Observation",
    )
    assert tuple(
        field.name for field in abductive.record_contracts["AbductionInput"].fields
    ) == ("background", "observation")
    abductive_result = abductive.aliases["Abductive"].result
    assert abductive_result is not None
    assert abductive_result.render() == "Hypothesis"
    deductive = method_modules["deductive"]
    assert deductive.type_parameters["Deductive"] == ("Conclusion", "Premises")
    assert deductive.type_parameters["DeductionInput"] == ("Premises",)
    assert tuple(
        field.name for field in deductive.record_contracts["DeductionInput"].fields
    ) == ("context",)
    deductive_result = deductive.aliases["Deductive"].result
    assert deductive_result is not None
    assert deductive_result.render() == "Conclusion"
    proven_result = deductive.aliases["ProvenDeductive"].result
    assert proven_result is not None
    assert proven_result.render() == (
        "Verified[value: Conclusion, Entails(source.context.value, value)]"
    )
    inductive = method_modules["inductive"]
    assert inductive.type_parameters["Inductive"] == (
        "Conclusion",
        "Dataset",
        "Population",
    )
    assert inductive.type_parameters["InductionInput"] == (
        "Dataset",
        "Population",
    )
    assert tuple(
        field.name for field in inductive.record_contracts["InductionInput"].fields
    ) == ("dataset", "population")
    inductive_result = inductive.aliases["Inductive"].result
    assert inductive_result is not None
    assert inductive_result.render() == "Conclusion"
    simplified_methods = {
        "analogical": (
            "Analogical",
            (
                "Conclusion",
                "SourceValue",
                "TargetValue",
                "CorrespondenceValue",
            ),
            "AnalogicalInput",
            ("SourceValue", "TargetValue", "CorrespondenceValue"),
            ("source", "target", "correspondence"),
        ),
        "contrastive": (
            "Contrastive",
            ("Conclusion", "Baseline", "Alternative"),
            "ContrastInput",
            ("Baseline", "Alternative"),
            ("baseline", "alternative"),
        ),
        "evidential": (
            "Evidential",
            ("Conclusion", "Observations", "Criteria"),
            "EvidentialInput",
            ("Observations", "Criteria"),
            ("observations", "criteria"),
        ),
        "model_based": (
            "ModelBased",
            ("Conclusion", "ModelValue", "InputValues"),
            "ModelInput",
            ("ModelValue", "InputValues"),
            ("model", "inputs"),
        ),
        "refutational": (
            "Refutational",
            ("Conclusion", "Subject", "Search"),
            "RefutationInput",
            ("Subject", "Search"),
            ("subject", "search"),
        ),
    }
    for module_name, (
        method,
        method_parameters,
        input_name,
        input_parameters,
        input_fields,
    ) in simplified_methods.items():
        module = method_modules[module_name]
        assert set(module.aliases) == {method}
        assert set(module.record_contracts) == {input_name}
        assert module.type_parameters[method] == method_parameters
        assert module.type_parameters[input_name] == input_parameters
        assert (
            tuple(field.name for field in module.record_contracts[input_name].fields)
            == input_fields
        )

    relations = checked("libs/prism/reasoning/relations.prism")
    expected_relations = {
        "Requires": "Required",
        "Assume": "Assumed",
        "Test": "Tested",
        "Calibrate": "CalibratedRelation",
        "Transfer": "Transferred",
        "Probe": "Probed",
        "Preserve": "Preserved",
    }
    for relation, certificate_name in expected_relations.items():
        contract = relations.callable_contracts[relation]
        assert contract.kind == "relation"
        assert len(contract.parameters) == 2
        assert contract.result.name == certificate_name

    for certificate_name in (
        "Required",
        "Assumed",
        "Tested",
        "CalibratedRelation",
        "Transferred",
        "Probed",
    ):
        assert tuple(
            field.name for field in relations.record_contracts[certificate_name].fields
        ) == ("source", "target")

    builders = checked("libs/prism/reasoning/relation_builders.prism")
    for relation, certificate_name in expected_relations.items():
        contract = builders.callable_contracts[f"build_{relation.lower()}"]
        assert len(contract.parameters) == 2
        assert contract.result.name == certificate_name
        assert contract.effects == ()


def test_module_resolver_accepts_library_modules() -> None:
    loader = WorkspaceModuleLoader(project_root=ROOT, entry_points=False)
    from prism.language.core import CallableContract, Parameter, RecordContract
    from prism.language.developer import parse_source, parse_type
    from prism.language.developer.syntax import FunctionDecl, TypeDecl, WorkflowDecl

    def extract(program):
        callables = {
            item.name: CallableContract(
                item.name,
                tuple(
                    Parameter(parameter.name, parse_type(parameter.type.text))
                    for parameter in item.parameters
                ),
                parse_type(item.result.text),
                item.effects,
            )
            for item in program.declarations
            if isinstance(item, FunctionDecl | WorkflowDecl)
        }
        records = {
            item.name: RecordContract(
                item.name,
                tuple(
                    Parameter(field.name, parse_type(field.type.text))
                    for field in item.fields
                ),
            )
            for item in program.declarations
            if isinstance(item, TypeDecl) and item.fields
        }
        return callables, records

    resolver = ModuleResolver(
        loader,
        lambda source, path: parse_source(source, path),
        extract,
    )

    assert (
        resolver.resolve_export(
            "prism.reasoning.relation_builders", "build_requires"
        ).name
        == "build_requires"
    )
    assert "prism.reasoning.relation_builders" in loader.iter_workspace_modules()
