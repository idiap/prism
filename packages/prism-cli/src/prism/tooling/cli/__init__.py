# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Prism CLI distribution and command composition."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Literal, cast

import typer
from dotenv import load_dotenv
from prism.adapters.python import PythonEffectHandler
from prism.language import check as check_program
from prism.language import compile as compile_program
from prism.language import elaborate, parse_source
from prism.language.kernel import (
    Kernel,
    KernelError,
    deserialize_module,
    prelude_module,
)
from prism.runtime import (
    CompositeEffectHandler,
    EffectRecorder,
    EffectReplayService,
    FakeEffectHandler,
    FileArtifactStore,
)
from prism.runtime import (
    run as run_program,
)
from prism.runtime.replay import effect_record_from_dict
from prism.sdk.runtime import (
    LocalResourceResolver,
    load_workspace_knowledge,
)
from prism.sdk.workspace import WorkspaceModuleLoader, resolve_project_root
from prism.transpiler import (
    BuildError,
    build_hooks_module,
    build_skill_module,
)

load_dotenv()

app = typer.Typer(
    add_completion=False, no_args_is_help=True, help="Prism language toolchain."
)
workflow_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Optional workflow-platform commands.",
)
layout_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Optional document-layout commands.",
)
build_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Build external skills and hooks into typed Prism modules.",
)
app.add_typer(workflow_app, name="workflow")
app.add_typer(layout_app, name="layout")
app.add_typer(build_app, name="build")


def project_root(program_file: Path | None = None) -> Path:
    return resolve_project_root(program_file, fallback=Path.cwd())


def emit_json(payload: Any) -> None:
    typer.echo(json.dumps(_jsonable(payload), indent=2, sort_keys=True))


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(cast(Any, value)).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if isinstance(value, set | frozenset):
        return [_jsonable(item) for item in sorted(value, key=repr)]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _frontend(program_file: Path):
    source = program_file.read_text(encoding="utf-8")
    program = parse_source(source, path=str(program_file))
    checked = check_program(
        program, modules=WorkspaceModuleLoader(project_root=project_root(program_file))
    )
    return checked


@app.command("parse")
def parse(
    program_file: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """Parse a Prism program and emit its surface AST."""
    emit_json(
        parse_source(program_file.read_text(encoding="utf-8"), path=str(program_file))
    )


@app.command("check")
def check(
    program_file: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """Parse, resolve, and type-check a Prism program without executing effects."""
    checked = _frontend(program_file)
    core_module = checked.checked_module
    emit_json(
        {
            "status": "ok",
            "path": str(program_file),
            "declarations": sorted(checked.globals),
            "proof_goals": checked.proof_goals,
            "core_module": (
                {
                    "format": core_module.core_format_version,
                    "calculus": core_module.calculus_version,
                    "hash": core_module.content_hash,
                    "axioms": {
                        name: sorted(axioms)
                        for name, axioms in core_module.axiom_dependencies.items()
                    },
                }
                if core_module is not None
                else None
            ),
        }
    )


@app.command("compile")
def compile_command(
    program_file: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """Compile a checked Prism program to backend-neutral effect IR."""
    executable = compile_program(elaborate(_frontend(program_file)))
    emit_json(
        {
            "ir_version": executable.ir_version,
            "path": str(program_file),
            "entry_callable": executable.entry_callable,
            "declarations": executable.declarations,
            "module_hashes": executable.module_hashes,
            "core_module_hash": (
                executable.checked_module.content_hash
                if executable.checked_module is not None
                else None
            ),
        }
    )


@build_app.command("skill")
def build_skill(
    source: Path = typer.Argument(..., exists=True),
    contract: str = typer.Option(..., "--contract"),
    output: Path = typer.Option(..., "--out"),
) -> None:
    """Build one Open Agent Skill into a standalone typed Prism module."""

    try:
        result = build_skill_module(
            source,
            contract,
            output,
            modules=WorkspaceModuleLoader(project_root=project_root()),
        )
    except BuildError as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit_json(
        {
            "status": "built",
            "module": result.path,
            "export": result.export,
            "type": result.type,
        }
    )


@build_app.command("hooks")
def build_hooks(
    provider: Literal["codex", "claude"] = typer.Argument(...),
    source: Path = typer.Argument(..., exists=True),
    output: Path = typer.Option(..., "--out"),
) -> None:
    """Build a native Codex or Claude hook configuration into a typed module."""

    try:
        result = build_hooks_module(provider, source, output)
    except BuildError as exc:
        raise typer.BadParameter(str(exc)) from exc
    emit_json(
        {
            "status": "built",
            "module": result.path,
            "export": result.export,
            "type": result.type,
        }
    )


@app.command("run")
def run_command(
    program_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    handler_name: str = typer.Option(
        "fake", "--handler", help="Material handler: fake, codex, or litellm."
    ),
    output_path: Path | None = typer.Option(None, "--output"),
) -> None:
    """Compile and execute a Prism program through installed effect handlers."""
    root = project_root(program_file)
    executable = compile_program(elaborate(_frontend(program_file)))
    if handler_name == "fake":
        material_handler = FakeEffectHandler.accepting_common_standards()
    elif handler_name == "codex":
        from prism.adapters.codex import CodexEffectHandler

        material_handler = CodexEffectHandler.from_environment()
    elif handler_name == "litellm":
        from prism.adapters.litellm import LiteLLMEffectHandler

        material_handler = LiteLLMEffectHandler.from_environment()
    else:
        raise typer.BadParameter(f"unsupported handler: {handler_name}")
    knowledge_broker = load_workspace_knowledge(root)
    effect_recorder = (
        EffectRecorder(FileArtifactStore(output_path.with_suffix(".artifacts")))
        if output_path is not None
        else EffectRecorder()
    )
    output = run_program(
        executable,
        handler=CompositeEffectHandler((PythonEffectHandler(), material_handler)),
        kernel=Kernel(
            executable.checked_module.environment
            if executable.checked_module is not None
            else None
        ),
        resource_resolver=LocalResourceResolver(root),
        knowledge_broker=knowledge_broker,
        effect_recorder=effect_recorder,
    )
    payload = _jsonable(output.to_dict())
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    emit_json(payload)
    if output.status != "accepted":
        raise typer.Exit(1)


@app.command("verify-run")
def verify_run_command(
    result_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    mode: str = typer.Option(
        "offline", "--mode", help="Verification mode: offline or live."
    ),
) -> None:
    """Recheck the native core module and verify or replay persisted effects."""

    if mode not in {"offline", "live"}:
        raise typer.BadParameter("--mode must be `offline` or `live`")
    replay_mode = cast(Literal["offline", "live"], mode)
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    try:
        module_report = _verify_checked_module(payload)
    except KernelError as exc:
        emit_json(
            {
                "mode": mode,
                "status": "failed",
                "reports": [],
                "checked_module": {
                    "status": "failed",
                    "diagnostics": [str(exc)],
                },
            }
        )
        raise typer.Exit(1) from exc
    raw_records = payload.get("effect_records", {})
    if not isinstance(raw_records, dict):
        raise typer.BadParameter("run result does not contain an effect-record mapping")
    recorder = EffectRecorder(FileArtifactStore(result_file.with_suffix(".artifacts")))
    records = {
        record_id: effect_record_from_dict(record)
        for record_id, record in raw_records.items()
    }
    recorder.records.update(records)
    handler = None
    if mode == "live":
        handlers: list[Any] = [PythonEffectHandler()]
        record_handlers = {record.invocation.handler for record in records.values()}
        if "codex" in record_handlers:
            from prism.adapters.codex import CodexEffectHandler

            handlers.append(CodexEffectHandler.from_environment())
        if "litellm" in record_handlers:
            from prism.adapters.litellm import LiteLLMEffectHandler

            handlers.append(LiteLLMEffectHandler.from_environment())
        if "fake" in record_handlers:
            handlers.append(FakeEffectHandler.accepting_common_standards())
        handler = CompositeEffectHandler(handlers)
    service = EffectReplayService(recorder, handler=handler)
    reports = [service.verify(record, mode=replay_mode) for record in records.values()]
    response = {
        "mode": mode,
        "status": _replay_status(reports),
        "reports": reports,
        "checked_module": module_report,
    }
    if mode == "live":
        comparison_ids = {
            report.comparison_record_id
            for report in reports
            if report.comparison_record_id
        }
        recheck_path = result_file.with_suffix(".rechecks.json")
        recheck_payload = {
            **response,
            "effect_records": {
                record_id: recorder.records[record_id]
                for record_id in sorted(comparison_ids)
                if record_id in recorder.records
            },
        }
        recheck_path.write_text(
            json.dumps(_jsonable(recheck_payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        response["recheck_path"] = str(recheck_path)
    emit_json(response)
    if any(report.status in {"failed", "unavailable"} for report in reports):
        raise typer.Exit(1)


def _replay_status(reports) -> str:
    if any(report.status == "failed" for report in reports):
        return "failed"
    if any(report.status == "unavailable" for report in reports):
        return "unavailable"
    if any(report.status == "changed" for report in reports):
        return "changed"
    return "verified"


def _verify_checked_module(payload: dict[str, Any]) -> dict[str, Any] | None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return None
    raw_module = metadata.get("checked_module")
    if raw_module is None:
        return None
    checked = deserialize_module(
        json.dumps(raw_module, sort_keys=True),
        {"Prism.Prelude": prelude_module()},
    )
    return {
        "status": "verified",
        "name": checked.name,
        "hash": checked.content_hash,
        "axioms": {
            name: sorted(axioms) for name, axioms in checked.axiom_dependencies.items()
        },
    }


@workflow_app.command("validate")
def validate_workflow(
    diagram_file: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    from prism.platform.workflow.diagram.service import WorkflowDiagramService

    service = WorkflowDiagramService(project_root=project_root())
    spec = service.load_diagram(diagram_file)
    emit_json(
        {
            "status": "ok",
            "name": spec.name,
            "execution_order": service.execution_order(spec),
        }
    )


def _layout_service():
    from prism.platform.libraries import LibraryRuntimeRegistry

    hook = LibraryRuntimeRegistry.load(project_root()).first_hook(
        "document_layout_service"
    )
    return hook(project_root=project_root())


def _require_layout_extension(path: Path) -> None:
    if path.suffix != ".prism-layout":
        raise typer.BadParameter(
            "document-layout files must use the `.prism-layout` extension"
        )


@layout_app.command("check")
def check_layout(
    layout_file: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    _require_layout_extension(layout_file)
    service = _layout_service()
    compiled = service.compile(service.load(layout_file))
    emit_json(
        {
            "status": "ok",
            "layout": str(layout_file),
            "invocation_count": len(compiled.invocations),
            "invocations": [
                item.model_dump(mode="json") for item in compiled.invocations
            ],
            "section_count": len(compiled.resolved.plan.sections),
        }
    )


@layout_app.command("navigation")
def layout_navigation(
    layout_file: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    _require_layout_extension(layout_file)
    emit_json(_layout_service().navigation_index(layout_file).model_dump(mode="json"))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
