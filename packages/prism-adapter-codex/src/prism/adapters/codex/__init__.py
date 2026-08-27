# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Codex CLI implementation of the typed ``AI.Generate`` effect."""

from __future__ import annotations

import json
import os

# Process execution is the adapter's purpose; it uses an argument vector, not a shell.
import subprocess  # nosec B404
import tempfile
from collections.abc import Mapping
from math import isfinite
from pathlib import Path
from typing import Any, Callable

from prism.language.core import Err, GeneratedValue, Ok, RecordValue
from prism.language.effects import EffectRequest, EffectResult

CodexRunner = Callable[..., subprocess.CompletedProcess[str]]


class CodexConfigurationError(RuntimeError):
    pass


class CodexResponseError(RuntimeError):
    pass


class CodexEffectHandler:
    """Execute structured generation through an isolated ``codex exec`` process."""

    def __init__(
        self,
        *,
        executable: str = "codex",
        model: str | None = None,
        profile: str | None = None,
        timeout_seconds: float | None = None,
        runner: CodexRunner | None = None,
    ) -> None:
        if not executable.strip():
            raise CodexConfigurationError("Codex executable cannot be empty")
        if timeout_seconds is not None and (
            timeout_seconds <= 0 or not isfinite(timeout_seconds)
        ):
            raise CodexConfigurationError("Codex timeout must be greater than zero")
        self.executable = executable
        self.model = model
        self.profile = profile
        self.timeout_seconds = timeout_seconds
        self._runner = runner or subprocess.run

    @classmethod
    def from_environment(
        cls, *, runner: CodexRunner | None = None
    ) -> "CodexEffectHandler":
        timeout_value = os.environ.get("PRISM_CODEX_TIMEOUT_SECONDS")
        try:
            timeout = float(timeout_value) if timeout_value else None
        except ValueError as exc:
            raise CodexConfigurationError(
                "PRISM_CODEX_TIMEOUT_SECONDS must be a positive number"
            ) from exc
        return cls(
            executable=os.environ.get("PRISM_CODEX_EXECUTABLE", "codex"),
            model=os.environ.get("PRISM_CODEX_MODEL") or None,
            profile=os.environ.get("PRISM_CODEX_PROFILE") or None,
            timeout_seconds=timeout,
            runner=runner,
        )

    def handles(self, symbol: str, effects: tuple[str, ...]) -> bool:
        return symbol == "generate" and "AI.Generate" in effects

    def execute(self, request: EffectRequest) -> EffectResult:
        if not request.arguments:
            return self._failure(request, "generate requires a typed request")
        schema = request.metadata.get("output_schema")
        if not isinstance(schema, Mapping):
            return self._failure(request, "generate requires a typed output schema")

        prompt_value = _json_value(request.arguments[0])
        prompt = _generation_prompt(prompt_value)
        hook_configurations = request.named_arguments.get("hooks", ())
        try:
            native_hooks = _codex_hooks(hook_configurations)
        except CodexConfigurationError as exc:
            return self._failure(request, str(exc))
        public_schema = _without_prism_extensions(schema)
        command: list[str] = [
            self.executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--color",
            "never",
        ]
        if self.model:
            command.extend(("--model", self.model))
        if self.profile:
            command.extend(("--profile", self.profile))

        try:
            with tempfile.TemporaryDirectory(prefix="prism-codex-") as directory:
                working_directory = Path(directory)
                schema_path = working_directory / "output-schema.json"
                schema_path.write_text(
                    json.dumps(public_schema, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                if native_hooks:
                    hook_directory = working_directory / ".codex"
                    hook_directory.mkdir()
                    (hook_directory / "hooks.json").write_text(
                        json.dumps(_merge_hooks(native_hooks), indent=2, sort_keys=True)
                        + "\n",
                        encoding="utf-8",
                    )
                    command.append("--dangerously-bypass-hook-trust")
                completed = self._runner(
                    [*command, "--output-schema", str(schema_path), "-"],
                    input=prompt,
                    text=True,
                    capture_output=True,
                    check=False,
                    cwd=working_directory,
                    timeout=self.timeout_seconds,
                )
        except FileNotFoundError:
            return self._failure(
                request,
                f"Codex executable `{self.executable}` was not found; install or "
                "configure the Codex CLI",
            )
        except subprocess.TimeoutExpired:
            detail = (
                f" after {self.timeout_seconds:g} seconds"
                if self.timeout_seconds is not None
                else ""
            )
            return self._failure(request, f"codex exec timed out{detail}")
        except OSError as exc:
            return self._failure(request, f"could not start codex exec: {exc}")

        if completed.returncode != 0:
            detail = _process_detail(completed)
            message = f"codex exec failed with exit code {completed.returncode}"
            if detail:
                message += f": {detail}"
            return self._failure(request, message)

        try:
            payload = _response_payload(completed.stdout)
            generated = _decode_value(payload, schema)
        except (CodexResponseError, json.JSONDecodeError) as exc:
            return self._failure(request, f"structured generation failed: {exc}")

        model_name = self.model or "configured-default"
        value = GeneratedValue(generated, f"codex:{model_name}")
        return EffectResult(
            Ok(value),
            request.result_type,
            provenance={"provider": "codex", "model": model_name},
            replay_artifacts={
                "model": model_name,
                "prompt": prompt_value,
                "output": payload,
            },
            executor="codex",
        )

    def _failure(self, request: EffectRequest, message: str) -> EffectResult:
        model_name = self.model or "configured-default"
        return EffectResult(
            Err(message),
            request.result_type,
            provenance={"provider": "codex", "model": model_name},
            executor="codex",
        )


def _generation_prompt(value: Any) -> str:
    instructions = (
        "You are the model backend for one PRISM AI.Generate effect. Use only "
        "the supplied request and activated instructions. Do not inspect files, "
        "run commands, or call tools. Return only the JSON value required by the "
        "provided output schema. Provide concise rationale fields when the schema "
        "requests them, but do not provide private chain-of-thought."
    )
    return (
        instructions
        + "\n\nPRISM AI.Generate request:\n"
        + json.dumps(value, indent=2, sort_keys=True)
    )


def _codex_hooks(value: Any) -> tuple[dict[str, Any], ...]:
    if value in (None, (), []):
        return ()
    if not isinstance(value, tuple | list):
        raise CodexConfigurationError("agent hooks must be typed native hook artifacts")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, tuple | list) or len(item) != 2:
            raise CodexConfigurationError("invalid native hook artifact")
        provider, configuration = item
        if provider != "Codex":
            raise CodexConfigurationError(
                f"Codex execution cannot activate Hooks[{provider}]"
            )
        try:
            parsed = json.loads(configuration)
        except (TypeError, json.JSONDecodeError) as exc:
            raise CodexConfigurationError(
                "invalid built Codex hook configuration"
            ) from exc
        if not isinstance(parsed, dict) or not isinstance(parsed.get("hooks"), dict):
            raise CodexConfigurationError("invalid built Codex hook configuration")
        result.append(parsed)
    return tuple(result)


def _merge_hooks(configurations: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    merged: dict[str, Any] = {"hooks": {}}
    for configuration in configurations:
        for event, groups in configuration["hooks"].items():
            merged["hooks"].setdefault(event, []).extend(groups)
    return merged


def _json_value(value: Any) -> Any:
    if isinstance(value, RecordValue):
        return {
            name: _json_value(field_value) for name, field_value in value.fields.items()
        }
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    return value


def _without_prism_extensions(schema: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: (
            _without_prism_extensions(value)
            if isinstance(value, Mapping)
            else (
                [
                    (
                        _without_prism_extensions(item)
                        if isinstance(item, Mapping)
                        else item
                    )
                    for item in value
                ]
                if isinstance(value, list)
                else value
            )
        )
        for key, value in schema.items()
        if not key.startswith("x-prism-")
    }


def _response_payload(stdout: str) -> Any:
    if not stdout.strip():
        raise CodexResponseError("Codex returned no structured content")
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CodexResponseError("Codex returned invalid JSON") from exc


def _decode_value(value: Any, schema: Mapping[str, Any]) -> Any:
    if "anyOf" in schema:
        if value is None:
            return None
        options = [item for item in schema["anyOf"] if item.get("type") != "null"]
        if not options:
            raise CodexResponseError("output schema has no non-null option")
        return _decode_value(value, options[0])
    schema_type = schema.get("type")
    if schema_type is not None and not isinstance(schema_type, str):
        raise CodexResponseError("output schema type must be a string")
    if schema_type == "object":
        if not isinstance(value, Mapping):
            raise CodexResponseError("model output must be a JSON object")
        properties = schema.get("properties", {})
        required = schema.get("required", ())
        missing = [name for name in required if name not in value]
        unknown = [name for name in value if name not in properties]
        if missing:
            raise CodexResponseError(
                "model output is missing fields: " + ", ".join(missing)
            )
        if unknown and schema.get("additionalProperties") is False:
            raise CodexResponseError(
                "model output has unknown fields: " + ", ".join(unknown)
            )
        fields = {
            name: _decode_value(value[name], field_schema)
            for name, field_schema in properties.items()
            if name in value
        }
        record_name = schema.get("x-prism-record")
        return RecordValue(str(record_name), fields) if record_name else fields
    if schema_type == "array":
        if not isinstance(value, list):
            raise CodexResponseError("model output must be a JSON array")
        return [_decode_value(item, schema["items"]) for item in value]
    expected_python = {
        "boolean": bool,
        "integer": int,
        "number": (int, float),
        "string": str,
    }.get(schema_type or "")
    if expected_python is not None:
        if schema_type in {"integer", "number"} and isinstance(value, bool):
            raise CodexResponseError(f"model output must be {schema_type}")
        if not isinstance(value, expected_python):
            raise CodexResponseError(f"model output must be {schema_type}")
    return value


def _process_detail(completed: subprocess.CompletedProcess[str]) -> str:
    detail = (completed.stderr or completed.stdout).strip()
    if len(detail) > 2000:
        return detail[:1997] + "..."
    return detail
