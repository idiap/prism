# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Runtime-backed execution and run-history service for Prism tooling."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from prism.adapters.python import PythonEffectHandler
from prism.language import compile as compile_program
from prism.language import elaborate
from prism.language.kernel import Kernel
from prism.runtime import (
    CompositeEffectHandler,
    EffectRecorder,
    FakeEffectHandler,
    FileArtifactStore,
    run,
)
from prism.sdk.runtime import LocalResourceResolver, load_workspace_knowledge
from prism.sdk.workspace import resolve_project_root
from prism.tooling.lsp.service import PrismLanguageService
from prism.tooling.protocol import PrismIdeRunResult


class PrismWorkbenchService:
    def __init__(
        self,
        *,
        project_root: Path | None = None,
        runs_root: Path | None = None,
        language_service: PrismLanguageService | None = None,
    ) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.runs_root = (runs_root or self.project_root).resolve()
        self.language = language_service or PrismLanguageService(
            project_root=self.project_root
        )

    def run_document(
        self,
        *,
        document_path: Path,
        document_text: str | None = None,
        backend_name: str = "fake",
        model: str | None = None,
    ) -> PrismIdeRunResult:
        source = (
            document_text
            if document_text is not None
            else document_path.read_text(encoding="utf-8")
        )
        checked_result = self.language.check_document(
            document_path=document_path, document_text=source
        )
        if checked_result.status == "invalid":
            return self._persist(
                PrismIdeRunResult(
                    status="failed",
                    backend=self._backend_name(backend_name),
                    model=model,
                    document_path=str(document_path.resolve()),
                    message="Document has syntax or type errors.",
                    diagnostics=checked_result.diagnostics,
                )
            )
        created_at, run_id, run_path = self._new_run_location(
            str(document_path.resolve())
        )
        root = resolve_project_root(document_path, fallback=self.project_root)
        artifact_store = FileArtifactStore(run_path.with_suffix(".artifacts"))
        effect_recorder = EffectRecorder(artifact_store)
        try:
            checked = self.language.checked_document(
                document_path=document_path, document_text=source
            )
            executable = compile_program(elaborate(checked))
            material = self._material_handler(backend_name=backend_name, model=model)
            knowledge_broker = load_workspace_knowledge(root)
            output = run(
                executable,
                handler=CompositeEffectHandler((PythonEffectHandler(), material)),
                kernel=self._kernel(executable, knowledge_broker),
                resource_resolver=LocalResourceResolver(root),
                knowledge_broker=knowledge_broker,
                effect_recorder=effect_recorder,
            ).to_dict()
        except Exception as exc:
            return self._persist(
                PrismIdeRunResult(
                    status="failed",
                    backend=self._backend_name(backend_name),
                    model=model,
                    document_path=str(document_path.resolve()),
                    message=str(exc),
                    diagnostics=[self.language.diagnostic(exc, source)],
                ),
                created_at=created_at,
                run_id=run_id,
                path=run_path,
                artifact_store=artifact_store,
            )
        return self._persist(
            PrismIdeRunResult(
                status="completed",
                backend=self._backend_name(backend_name),
                model=model,
                document_path=str(document_path.resolve()),
                message=f"Run completed with Prism status `{output.get('status')}`.",
                output=output,
            ),
            created_at=created_at,
            run_id=run_id,
            path=run_path,
            artifact_store=artifact_store,
        )

    def latest_run_for_document(
        self, *, document_path: Path
    ) -> PrismIdeRunResult | None:
        runs = self.runs_for_document(document_path=document_path)
        return runs[0] if runs else None

    def runs_for_document(self, *, document_path: Path) -> list[PrismIdeRunResult]:
        target = str(document_path.resolve())
        runs: list[tuple[str, int, str, PrismIdeRunResult]] = []
        for path in self._runs_dir().glob("*.json"):
            try:
                result = PrismIdeRunResult.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                modified = path.stat().st_mtime_ns
            except (OSError, ValueError):
                continue
            if result.document_path == target:
                artifact_path = path.with_suffix(".artifacts")
                if artifact_path.is_dir():
                    result = self._resolve_effect_artifacts(
                        result, FileArtifactStore(artifact_path)
                    )
                runs.append((result.run_created_at or "", modified, str(path), result))
        return [result for _, _, _, result in sorted(runs, reverse=True)]

    def delete_run_for_document(self, *, document_path: Path, run_id: str) -> bool:
        target = str(document_path.resolve())
        for path in self._runs_dir().glob("*.json"):
            try:
                result = PrismIdeRunResult.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                continue
            if result.document_path == target and result.run_id == run_id:
                path.unlink()
                artifact_path = path.with_suffix(".artifacts")
                if artifact_path.is_dir():
                    shutil.rmtree(artifact_path)
                return True
        return False

    def _material_handler(self, *, backend_name: str, model: str | None):
        if backend_name == "fake":
            return FakeEffectHandler.accepting_common_standards()
        if backend_name == "litellm":
            if not model:
                raise ValueError("A LiteLLM model identifier is required.")
            from prism.adapters.litellm import LiteLLMEffectHandler

            return LiteLLMEffectHandler(model=model)
        raise ValueError(f"Unsupported Prism backend `{backend_name}`.")

    def _kernel(self, executable, knowledge_broker=None) -> Kernel:
        return Kernel(
            executable.checked_module.environment
            if executable.checked_module is not None
            else None
        )

    def _backend_name(self, backend_name: str) -> Literal["fake", "litellm"]:
        return "litellm" if backend_name == "litellm" else "fake"

    def _persist(
        self,
        result: PrismIdeRunResult,
        *,
        created_at: str | None = None,
        run_id: str | None = None,
        path: Path | None = None,
        artifact_store: FileArtifactStore | None = None,
    ) -> PrismIdeRunResult:
        if created_at is None or run_id is None or path is None:
            created_at, run_id, path = self._new_run_location(result.document_path)
        result = result.model_copy(
            update={
                "run_id": run_id,
                "run_path": str(path),
                "run_created_at": created_at,
            }
        )
        self._runs_dir().mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if artifact_store is None:
            return result
        return self._resolve_effect_artifacts(result, artifact_store)

    def _new_run_location(self, document_path: str) -> tuple[str, str, Path]:
        created_at = (
            datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        )
        run_id = (
            f"{created_at.replace(':', '').replace('.', '')}-{uuid.uuid4().hex[:8]}"
        )
        path = self._runs_dir() / f"{self._stem(document_path)}-{run_id}.json"
        return created_at, run_id, path

    def _resolve_effect_artifacts(
        self,
        result: PrismIdeRunResult,
        artifact_store: FileArtifactStore,
    ) -> PrismIdeRunResult:
        resolved = result.model_copy(deep=True)
        if resolved.output is None:
            return resolved
        records = resolved.output.get("effect_records")
        if not isinstance(records, dict):
            return resolved
        for record in records.values():
            if not isinstance(record, dict):
                continue
            invocation = record.get("invocation")
            observation = record.get("observation")
            if isinstance(invocation, dict):
                self._resolve_artifact_field(
                    record,
                    "input_payload",
                    invocation.get("input_artifact"),
                    artifact_store,
                )
            if isinstance(observation, dict):
                self._resolve_artifact_field(
                    record,
                    "output_payload",
                    observation.get("output_artifact"),
                    artifact_store,
                )
        return resolved

    def _resolve_artifact_field(
        self,
        record: dict[str, object],
        field: str,
        reference: object,
        artifact_store: FileArtifactStore,
    ) -> None:
        if not isinstance(reference, dict):
            return
        digest = reference.get("digest")
        if not isinstance(digest, str):
            return
        try:
            if artifact_store.verify(digest):
                record[field] = artifact_store.get(digest)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return

    def _runs_dir(self) -> Path:
        return self.runs_root / ".prism" / "runs"

    def _stem(self, document_path: str) -> str:
        document = Path(document_path)
        digest = hashlib.sha256(document_path.encode("utf-8")).hexdigest()[:12]
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", document.stem).strip(".-") or "document"
        return f"{safe}-{digest}"
