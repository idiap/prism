# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Stdio gateway composing the backend-neutral language service with an optional workbench."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

from prism.tooling.lsp.service import PrismLanguageService
from prism.tooling.protocol import PrismIdeHealthResponse


class PrismIdeStdioServer:
    def __init__(self, *, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.language = PrismLanguageService(project_root=self.project_root)
        self._workbench_service = None

    def serve(self) -> int:
        for raw_line in sys.stdin:
            if not raw_line.strip():
                continue
            try:
                response = self._handle(json.loads(raw_line))
            except Exception as exc:  # pragma: no cover - transport guard
                response = {
                    "id": None,
                    "ok": False,
                    "error": {"message": str(exc), "traceback": traceback.format_exc()},
                }
            sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
            sys.stdout.flush()
        return 0

    def _handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = payload.get("id")
        try:
            return {
                "id": request_id,
                "ok": True,
                "result": self._dispatch(
                    str(payload.get("method") or ""), payload.get("params") or {}
                ),
            }
        except Exception as exc:
            return {"id": request_id, "ok": False, "error": {"message": str(exc)}}

    def _dispatch(self, method: str, params: dict[str, Any]) -> Any:
        if method == "health":
            return PrismIdeHealthResponse().model_dump(mode="json")
        path = Path(str(params.get("document_path") or "")).resolve()
        if method == "checkDocument":
            return self.language.check_document(
                document_path=path,
                document_text=params.get("document_text"),
            ).model_dump(mode="json")
        if method == "definitionAt":
            result = self.language.definition_at(
                document_path=path,
                document_text=params.get("document_text"),
                line=int(params.get("line") or 0),
                character=int(params.get("character") or 0),
            )
            return result.model_dump(mode="json") if result else None
        if method == "completionAt":
            return [
                item.model_dump(mode="json")
                for item in self.language.completion_at(
                    document_path=path,
                    document_text=params.get("document_text"),
                    line=int(params.get("line") or 0),
                    character=int(params.get("character") or 0),
                )
            ]
        workbench = self._workbench()
        if method == "runDocument":
            return workbench.run_document(
                document_path=path,
                document_text=params.get("document_text"),
                backend_name=str(params.get("backend_name") or "fake"),
                model=params.get("model") or None,
            ).model_dump(mode="json")
        if method == "latestRunForDocument":
            result = workbench.latest_run_for_document(document_path=path)
            return result.model_dump(mode="json") if result else None
        if method == "runsForDocument":
            return [
                item.model_dump(mode="json")
                for item in workbench.runs_for_document(document_path=path)
            ]
        if method == "deleteRunForDocument":
            return workbench.delete_run_for_document(
                document_path=path, run_id=str(params.get("run_id") or "")
            )
        raise ValueError(f"Unsupported IDE method: {method}")

    def _workbench(self):
        if self._workbench_service is None:
            from prism.tooling.workbench.service import PrismWorkbenchService

            self._workbench_service = PrismWorkbenchService(
                project_root=self.project_root,
                language_service=self.language,
            )
        return self._workbench_service


def main() -> int:
    return PrismIdeStdioServer().serve()


if __name__ == "__main__":
    raise SystemExit(main())
