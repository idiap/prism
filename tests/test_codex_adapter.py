# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from prism.adapters.codex import CodexConfigurationError, CodexEffectHandler
from prism.language.core import CoreType, Err, Ok, RecordValue
from prism.language.effects import EffectRequest


def _request(*, hooks: tuple[tuple[str, str], ...] = ()) -> EffectRequest:
    analysis = CoreType("Analysis")
    named_arguments = {"hooks": hooks} if hooks else {}
    return EffectRequest(
        call_id="call:1",
        symbol="generate",
        arguments=(
            RecordValue(
                "AnalysisRequest",
                {"claim": "tax is theft", "standard": "necessary conditions"},
            ),
        ),
        named_arguments=named_arguments,
        result_type=CoreType(
            "Result",
            (CoreType("Generated", (analysis,)), CoreType("ModelFailure")),
        ),
        effects=("AI.Generate",),
        metadata={
            "output_type": "Analysis",
            "output_schema": {
                "type": "object",
                "title": "Analysis",
                "x-prism-record": "Analysis",
                "properties": {
                    "supported": {"type": "boolean"},
                    "rationale": {"type": "string"},
                },
                "required": ["supported", "rationale"],
                "additionalProperties": False,
            },
        },
    )


def test_codex_handler_runs_isolated_structured_generation(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict]] = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        schema_path = Path(command[command.index("--output-schema") + 1])
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert "x-prism-record" not in schema
        assert kwargs["cwd"] == schema_path.parent
        hooks_path = kwargs["cwd"] / ".codex" / "hooks.json"
        assert json.loads(hooks_path.read_text())["hooks"]["Stop"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "supported": False,
                    "rationale": "A necessary condition is absent.",
                }
            ),
            stderr="progress stays on stderr",
        )

    handler = CodexEffectHandler(
        executable="codex-test",
        model="test-model",
        profile="test-profile",
        timeout_seconds=45,
        runner=runner,
    )
    result = handler.execute(
        _request(
            hooks=(
                (
                    "Codex",
                    json.dumps(
                        {
                            "hooks": {
                                "Stop": [
                                    {"hooks": [{"type": "command", "command": "check"}]}
                                ]
                            }
                        }
                    ),
                ),
            )
        )
    )

    assert isinstance(result.value, Ok)
    assert result.value.value.producer == "codex:test-model"
    generated = result.value.value.value
    assert generated == RecordValue(
        "Analysis",
        {
            "supported": False,
            "rationale": "A necessary condition is absent.",
        },
    )
    assert result.executor == "codex"
    assert result.provenance == {"provider": "codex", "model": "test-model"}
    assert result.replay_artifacts["output"] == generated.fields

    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[:2] == ["codex-test", "exec"]
    assert "--ephemeral" in command
    assert "--dangerously-bypass-hook-trust" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--skip-git-repo-check" in command
    assert command[command.index("--model") + 1] == "test-model"
    assert command[command.index("--profile") + 1] == "test-profile"
    assert command[-1] == "-"
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False
    assert kwargs["timeout"] == 45
    assert "tax is theft" in kwargs["input"]


def test_codex_handler_returns_model_failure_for_cli_errors() -> None:
    def runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command, 1, stdout="", stderr="authentication required"
        )

    result = CodexEffectHandler(runner=runner).execute(_request())

    assert isinstance(result.value, Err)
    assert result.value.error == (
        "codex exec failed with exit code 1: authentication required"
    )
    assert result.executor == "codex"


def test_codex_handler_rejects_invalid_structured_output() -> None:
    def runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"supported": "not-a-boolean", "rationale": "bad"}),
            stderr="",
        )

    result = CodexEffectHandler(runner=runner).execute(_request())

    assert isinstance(result.value, Err)
    assert result.value.error == (
        "structured generation failed: model output must be boolean"
    )


def test_codex_handler_reads_environment_configuration(monkeypatch) -> None:
    monkeypatch.setenv("PRISM_CODEX_EXECUTABLE", "/opt/codex")
    monkeypatch.setenv("PRISM_CODEX_MODEL", "configured-model")
    monkeypatch.setenv("PRISM_CODEX_PROFILE", "reasoning")
    monkeypatch.setenv("PRISM_CODEX_TIMEOUT_SECONDS", "12.5")

    handler = CodexEffectHandler.from_environment()

    assert handler.executable == "/opt/codex"
    assert handler.model == "configured-model"
    assert handler.profile == "reasoning"
    assert handler.timeout_seconds == 12.5


def test_codex_handler_rejects_invalid_timeout(monkeypatch) -> None:
    monkeypatch.setenv("PRISM_CODEX_TIMEOUT_SECONDS", "soon")

    with pytest.raises(
        CodexConfigurationError,
        match="PRISM_CODEX_TIMEOUT_SECONDS must be a positive number",
    ):
        CodexEffectHandler.from_environment()
