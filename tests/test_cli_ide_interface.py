# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

import json
from pathlib import Path

import pytest
from prism.tooling.cli import app
from typer.testing import CliRunner

RUNNER = CliRunner()


@pytest.mark.parametrize("version", [None, "10", "future"])
def test_verify_run_rejects_unsupported_trace_before_replay(tmp_path, version):
    result_file = tmp_path / "run.json"
    payload = {} if version is None else {"trace_version": version}
    result_file.write_text(json.dumps(payload), encoding="utf-8")
    result = _invoke_json("verify-run", str(result_file), expected_exit_code=1)
    assert result["status"] == "failed"
    assert "unsupported trace version" in result["diagnostics"][0]


def _invoke_json(*args: str, expected_exit_code: int = 0) -> dict:
    result = RUNNER.invoke(app, list(args))
    assert result.exit_code == expected_exit_code, result.stdout
    return json.loads(result.stdout)


def test_cli_build_skill_emits_a_checked_typed_module(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "review"
    source.mkdir()
    skill = source / "SKILL.md"
    skill.write_text(
        "---\nname: review\ndescription: Review a supplied repository\n---\n"
        "Review the supplied repository.\n",
        encoding="utf-8",
    )
    contracts = tmp_path / "contracts.prism"
    contracts.write_text("type ReviewTask:\n    request: String\n", encoding="utf-8")
    output = tmp_path / "review_skill"

    monkeypatch.chdir(tmp_path)
    payload = _invoke_json(
        "build",
        "skill",
        str(source),
        "--contract",
        "contracts.ReviewTask",
        "--out",
        str(output),
    )

    assert payload["status"] == "built"
    assert payload["type"] == "Skill[ReviewTask]"
    assert output.with_suffix(".prism").is_file()


def test_cli_discovers_generated_project_for_absolute_source_path(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "projects" / "artifact_acceptance_loop" / "prism_project"
    project.mkdir(parents=True)
    (project / "runtime.json").write_text(
        '{"handler": "fake", "workspace": "."}\n', encoding="utf-8"
    )
    (project / "artifact_acceptance_loop.prism").write_text(
        "type ArtifactAcceptanceCase:\n    name: String\n", encoding="utf-8"
    )
    reasoning = project / "reasoning.prism"
    reasoning.write_text(
        "from artifact_acceptance_loop import ArtifactAcceptanceCase\n",
        encoding="utf-8",
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.delenv("PRISM_PROJECT_ROOT", raising=False)
    monkeypatch.chdir(outside)

    payload = _invoke_json("check", str(reasoning))

    assert payload["status"] == "ok"
    assert "ArtifactAcceptanceCase" in payload["declarations"]


INSPECTION_SOURCE = """
type Step = Int -> Int
def identity(value: Int) -> Int:
    return value
reasoning Plan(value: Int) -> Int:
    sequence:
        [prepared: identity(value)]
        [result: Step(prepared)] with:
            output.producers = [literal, computed]
    return result
configured = Plan(result = identity)
def main() -> Int:
    return solve Plan(3) using configured(3)
"""


def test_cli_and_editor_share_occurrence_contracts_and_persisted_outcomes(tmp_path):
    from prism.language.developer.syntax import ReasoningDecl
    from prism.tooling.lsp.service import PrismLanguageService
    from prism.tooling.workbench.service import PrismWorkbenchService

    path = tmp_path / "inspection.prism"
    path.write_text(INSPECTION_SOURCE)
    cli = _invoke_json("check", str(path))
    language = PrismLanguageService(project_root=tmp_path)
    inspected = language.check_document(document_path=path)
    assert inspected.status == "valid"
    assert (
        json.loads(inspected.model_dump_json())["occurrence_contracts"]
        == cli["occurrence_contracts"]
    )
    symbols = {
        symbol.name: symbol
        for symbol in inspected.symbols
        if symbol.kind == "WorkflowNode"
    }
    assert (
        symbols["prepared"].metadata["declared_contract"]["execution_kind"]
        == "structural"
    )
    assert (
        symbols["prepared"].metadata["declared_contract"]["classification"][
            "archetype_state"
        ]
        == "not_applicable"
    )
    checked = language.checked_document(document_path=path)
    plan = next(
        declaration
        for declaration in checked.program.declarations
        if getattr(declaration, "name", None) == "Plan"
    )
    assert isinstance(plan, ReasoningDecl)
    assert language._reasoning_configuration_names(plan, checked) == ("result",)

    service = PrismWorkbenchService(project_root=tmp_path, runs_root=tmp_path)
    run = service.run_document(document_path=path)
    assert run.status == "completed"
    assert run.output is not None
    persisted = service.latest_run_for_document(document_path=path)
    assert persisted is not None and persisted.output is not None
    wire_output = json.loads(run.model_dump_json())["output"]
    assert persisted.output["trace"] == wire_output["trace"]
    declared = {
        contract["identity"]: contract for contract in cli["occurrence_contracts"]
    }
    references = {value["identity"] for value in run.output["provenance"]["values"]}
    nodes = [
        event for event in wire_output["trace"] if event["kind"] == "workflow-node"
    ]
    assert len(nodes) == 2
    for node in nodes:
        contract = node["metadata"]["declared_contract"]
        assert contract == declared[contract["identity"]]
        assert node["outcome"]["execution"] == "completed"
        assert node["outcome"]["contract"] == "satisfied"
        assert node["outcome"]["observed"][0]["assurance"] == "unchecked"
        assert all(
            value["reference"] in references for value in node["outcome"]["observed"]
        )


@pytest.mark.parametrize("version", [None, "10", "future"])
def test_workbench_reports_unsupported_persisted_trace(tmp_path, version):
    from prism.tooling.workbench.service import PrismWorkbenchService

    path = tmp_path / "inspection.prism"
    path.write_text(INSPECTION_SOURCE)
    service = PrismWorkbenchService(project_root=tmp_path, runs_root=tmp_path)
    result = service.run_document(document_path=path)
    assert result.run_path is not None
    persisted_path = Path(result.run_path)
    payload = json.loads(persisted_path.read_text())
    payload["output"]["trace_version"] = version
    persisted_path.write_text(json.dumps(payload))
    loaded = service.latest_run_for_document(document_path=path)
    assert loaded is not None
    assert loaded.status == "failed"
    assert loaded.output is None
    assert "unsupported trace version" in loaded.message
    assert loaded.run_id == result.run_id


def _installed_cli(project: Path, *arguments: str):
    import os
    import subprocess
    import sys
    import sysconfig

    executable = Path(sysconfig.get_path("scripts")) / "prism"
    assert executable.is_file(), "The active environment must install the prism CLI"
    return subprocess.run(
        [sys.executable, str(executable), *arguments],
        cwd=project,
        env={
            **os.environ,
            "NO_COLOR": "1",
            "TERM": "dumb",
            "PRISM_PROJECT_ROOT": str(project),
        },
        capture_output=True,
        text=True,
        timeout=120,
    )


def _cli_project(tmp_path: Path, *, examples=False):
    import shutil

    root = Path(__file__).resolve().parents[1]
    (tmp_path / "runtime.json").write_text('{"workspace": ".", "handler": "fake"}')
    if examples:
        shutil.copytree(root / "examples/language", tmp_path / "examples/language")
        shutil.copytree(root / "libs/prism", tmp_path / "libs/prism")
    return tmp_path


def _cli_pipeline(project: Path, path: Path):
    checked = _installed_cli(project, "check", str(path))
    assert checked.returncode == 0, checked.stderr
    checked_payload = json.loads(checked.stdout)
    compiled = _installed_cli(project, "compile", str(path))
    assert compiled.returncode == 0, compiled.stderr
    assert json.loads(compiled.stdout)["entry_callable"] == "main"
    persisted = project / "result.json"
    executed = _installed_cli(
        project, "run", str(path), "--handler", "fake", "--output", str(persisted)
    )
    assert executed.returncode == 0, executed.stderr
    payload = json.loads(persisted.read_text())
    assert payload == json.loads(executed.stdout)
    assert payload["trace_version"] == "11"
    assert payload["status"] == "accepted"
    return checked_payload, payload


def _persisted_ancestry(payload, reference):
    values = {value["identity"]: value for value in payload["provenance"]["values"]}
    activities = {
        activity["identity"]: activity
        for activity in payload["provenance"]["activities"]
    }
    visited = set()
    found = {}
    pending = [reference]
    while pending:
        identity = pending.pop()
        if identity in visited:
            continue
        visited.add(identity)
        value = values[identity]
        pending.extend(value["dependencies"])
        activity = activities[value["activity"]]
        if activity["identity"] not in found:
            found[activity["identity"]] = activity
            pending.extend(activity["inputs"])
    return list(found.values())


@pytest.mark.e2e
@pytest.mark.parametrize("example", ["strict_inference", "refinement_loop"])
def test_e2e_cli_examples_preserve_contracts_and_certificates(tmp_path, example):
    project = _cli_project(tmp_path, examples=True)
    checked, payload = _cli_pipeline(
        project, project / "examples/language" / example / "main.prism"
    )
    declared = {
        contract["identity"]: contract for contract in checked["occurrence_contracts"]
    }
    nodes = [event for event in payload["trace"] if event["kind"] == "workflow-node"]
    instances = {node["metadata"]["occurrence_instance_id"] for node in nodes}
    assert len(instances) == len(nodes)
    for node in nodes:
        contract = node["metadata"]["declared_contract"]
        assert contract["identity"] in declared
        assert (
            contract["classification"]
            == declared[contract["identity"]]["classification"]
        )
        assert contract["requirements"]
        assert node["outcome"]["execution"] == "completed"
        assert node["outcome"]["contract"] == "satisfied"
        assert all(value["reference"] for value in node["outcome"]["observed"])
    relations = [
        event for event in payload["trace"] if event["kind"] == "reasoning-relation"
    ]
    assert relations
    for relation in relations:
        assert relation["metadata"]["target_occurrence_instance"] in instances
        assert relation["metadata"]["certificate_valid"] is True
        assert relation["metadata"]["declared_relation"]["certificate_type"]
        certificate = relation["outcome"]["observed"][0]
        assert certificate["claim"] and certificate["certificate"]
    if example == "strict_inference":
        assert payload["result"] == {"value": 7}
        assert nodes[0]["outcome"]["observed"][0]["assurance"] == "unchecked"
        assert relations[0]["outcome"]["observed"][0]["assurance"] == "proved"
        assert relations[0]["outcome"]["observed"][0]["certificate"]["proof_hash"]
    else:
        assert payload["result"]["value"]["result"] is True
        plan = payload["result"]["value"]["value"]["value"]["fields"]
        assert plan["terminal"]["fields"]["angle_degrees"] == 0.0
        assert len([node for node in nodes if node["name"] == "finding"]) == 5
        candidate = next(node for node in nodes if node["name"] == "candidate")
        narrative = next(
            value
            for value in candidate["outcome"]["observed"]
            if value["path"][-1:] == ["strategy"]
        )
        ancestry = _persisted_ancestry(payload, narrative["reference"])
        generated = [
            activity for activity in ancestry if activity["kind"] == "generated"
        ]
        assert generated and all(activity["synthetic"] for activity in generated)
        assert all(
            activity["effect_record"] in payload["effect_records"]
            for activity in generated
        )
        final = next(node for node in nodes if node["name"] == "safe_plan")
        validated = next(
            value
            for value in final["outcome"]["observed"]
            if value["assurance"] == "validated"
        )
        assert validated["certificate"]["validator_hash"]
        assert any(
            activity["kind"] == "computed"
            for activity in _persisted_ancestry(payload, validated["reference"])
        )
        assert not any(
            event["kind"] == "kernel-check-accepted" for event in payload["trace"]
        )
        assert all(
            relation["outcome"]["observed"][0]["assurance"] == "supported"
            for relation in relations
        )


@pytest.mark.e2e
def test_e2e_cli_real_resource_transformation_retains_acquisition(tmp_path):
    import hashlib

    project = _cli_project(tmp_path)
    (project / "measurement.txt").write_text("measured")
    path = project / "main.prism"
    path.write_text("""resource: Resource[String] = embed("measurement.txt")
def annotate(value: String) -> String:
    return value + "!"
def transform(packet: Evidence[String]) -> Evidence[String]:
    return map_evidence(packet, transformation = annotate)
workflow ReadMeasurement(files: FileRead, clock: ClockRead) -> Evidence[String]
    fails SourceError ! {File.Read, Clock.Read}:
    sequence:
        [packet: resource_evidence(resource, files, clock)]
        [changed: transform(packet)]
    return changed
def main(files: FileRead, clock: ClockRead) -> Result[Evidence[String], SourceError] ! {File.Read, Clock.Read}:
    return solve ReadMeasurement(files, clock)
""")
    _, payload = _cli_pipeline(project, path)
    assert payload["result"]["value"]["value"] == "measured!"
    changed = next(
        event
        for event in payload["trace"]
        if event["kind"] == "workflow-node" and event["name"] == "changed"
    )
    observed = changed["outcome"]["observed"][0]
    assert observed["producer"] == "computed"
    assert observed["assurance"] == "unchecked"
    assert observed["claim"] is None and observed["certificate"] is None
    activities = _persisted_ancestry(payload, observed["reference"])
    acquired = [activity for activity in activities if activity["kind"] == "acquired"]
    assert len(acquired) == 1
    assert acquired[0]["source"] == "measurement.txt"
    assert acquired[0]["source_hash"] == hashlib.sha256(b"measured").hexdigest()
    assert acquired[0]["synthetic"] is False


NEGATIVE_CLI_SOURCES = {
    "forged_proof": """def Accepted(value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int) -> PolicyDecision:
    return accept_assessment("checked")
policy = material_policy[Int, Accepted(7), Never]("policy", evaluator = evaluate)
forged: Proof[Accepted(7)] = policy
def main() -> Proof[Accepted(7)]:
    return forged
""",
    "wrong_verified_value": """def Same(left: Nat, right: Nat) -> Prop:
    return left == right
def main() -> Result[Verified[value: Nat, Same(value, 7)], ProofError]:
    original: Nat = 7
    replacement: Nat = 9
    term = try elaborate_proof[Same(original, 7)]("rfl")
    proof = try kernel.check(term)
    return Ok(verify(replacement, proof))
""",
    "wrong_invocation": """type Step = Int -> Int
reasoning Plan(value: Int) -> Int:
    [result: Step(value)]
    return result
def identity(value: Int) -> Int:
    return value
configured = Plan(result = identity)
def main() -> Int:
    return solve Plan(1) using configured(9)
""",
    "rejected_support": """def Positive(value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int) -> PolicyDecision:
    return reject_assessment("evidence rejected")
policy = material_policy[Int, Positive(3), Never]("policy", evaluator = evaluate)
def main() -> Result[Supported[Positive(3)], SupportError]:
    assessment = try observe(3) |~[policy] Positive(3)
    return accept_support(assessment)
""",
}


@pytest.mark.e2e
@pytest.mark.parametrize("case", [*NEGATIVE_CLI_SOURCES, "wrong_returned_target"])
def test_e2e_cli_rejects_invalid_sources_at_the_required_boundary(tmp_path, case):
    project = _cli_project(tmp_path, examples=case == "wrong_returned_target")
    if case == "wrong_returned_target":
        directory = project / "examples/language/strict_inference"
        materializer = directory / "materialization.prism"
        materializer.write_text(
            materializer.read_text().replace("return approved", "return 9")
        )
        path = directory / "main.prism"
    else:
        path = project / "main.prism"
        path.write_text(NEGATIVE_CLI_SOURCES[case])
    checked = _installed_cli(project, "check", str(path))
    if case in {"forged_proof", "wrong_verified_value"}:
        assert checked.returncode != 0
        assert "type-" in checked.stderr
        assert "Proof" in checked.stderr or "verify" in checked.stderr
        return
    assert checked.returncode == 0, checked.stderr
    compiled = _installed_cli(project, "compile", str(path))
    assert compiled.returncode == 0, compiled.stderr
    persisted = project / "rejected.json"
    result = _installed_cli(
        project, "run", str(path), "--handler", "fake", "--output", str(persisted)
    )
    assert result.returncode != 0
    if case == "wrong_invocation":
        assert "arguments" in result.stderr
        assert not persisted.exists()
        return
    payload = json.loads(persisted.read_text())
    assert payload == json.loads(result.stdout)
    assert payload["status"] == "rejected"
    if case == "wrong_returned_target":
        relation = next(
            event for event in payload["trace"] if event["kind"] == "reasoning-relation"
        )
        assert relation["metadata"]["certificate_valid"] is False
        assert relation["outcome"]["contract"] == "rejected"
    else:
        policy = next(
            event for event in payload["trace"] if event["kind"] == "material-policy"
        )
        assert policy["metadata"]["disposition"] == "rejected"
        assert payload["result"]["error"]["decision"]["disposition"] == "rejected"
        assert not any(event["assurance"] == "Supported" for event in payload["trace"])
