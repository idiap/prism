# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
from prism.adapters.python import PythonEffectHandler
from prism.language import check, compile, elaborate, parse_source
from prism.language.core import CoreType, Err, Ok, RecordValue
from prism.language.developer import PrismTypeError
from prism.language.effects import EffectRequest, EffectResult
from prism.runtime import run

PROGRAM = """
type AddRequest:
    left: Int
    right: Int

type AddResponse:
    value: Int

def add(
    request: AddRequest,
    access: PythonCall,
) -> Result[AddResponse, PythonError] ! {Python.Call}:
    return python_call[AddResponse]("calculator.add", request, access)

def main(access: PythonCall) -> Result[AddResponse, PythonError] ! {Python.Call}:
    return add(AddRequest(left = 2, right = 3), access)
"""


def _add(request: EffectRequest) -> EffectResult:
    payload = request.arguments[0]
    assert isinstance(payload, RecordValue)
    response = RecordValue(
        "AddResponse",
        {"value": payload.fields["left"] + payload.fields["right"]},
    )
    return EffectResult(
        Ok(response),
        request.result_type,
        provenance={"implementation": "test-calculator"},
        executor="python:test-calculator",
    )


def _raise(_: EffectRequest) -> EffectResult:
    raise RuntimeError("calculation failed")


def _executable():
    return compile(elaborate(check(parse_source(PROGRAM))))


def _binding(function: str) -> dict[str, str]:
    return {"calculator.add": f"{__name__}:{function}"}


def test_python_call_executes_registered_callable() -> None:
    output = run(_executable(), handler=PythonEffectHandler(_binding("_add")))

    assert output.status == "accepted"
    assert output.result == Ok(RecordValue("AddResponse", {"value": 5}))
    effect = next(event for event in output.trace if event.kind == "effect")
    assert effect.name == "calculator.add"
    assert effect.metadata["effects"] == ("Python.Call",)


def test_python_exception_becomes_typed_failure() -> None:
    output = run(_executable(), handler=PythonEffectHandler(_binding("_raise")))

    assert output.status == "rejected"
    assert output.result == Err("RuntimeError: calculation failed")


def test_python_handler_does_not_handle_agent_tool_effects() -> None:
    handler = PythonEffectHandler(_binding("_add"))

    assert handler.handles("calculator.add", ("Python.Call",))
    assert not handler.handles("calculator.add", ("Tool.Call",))


def test_python_handler_enforces_runtime_permission() -> None:
    handler = PythonEffectHandler(_binding("_add"))
    request = EffectRequest(
        "call:unauthorized",
        "calculator.add",
        (),
        {},
        CoreType("Result", (CoreType("AddResponse"), CoreType("PythonError"))),
        ("Python.Call",),
    )

    with pytest.raises(PermissionError, match="requires PythonCall permission"):
        handler.execute(request)


def test_python_call_requires_explicit_permission() -> None:
    with pytest.raises(PrismTypeError, match="no explicit PythonCall permission"):
        check(
            parse_source("""
def main() -> String ! {Python.Call}:
    return "not called"
""")
        )


def test_python_call_cannot_introduce_protected_values() -> None:
    with pytest.raises(
        PrismTypeError,
        match="python_call.*cannot produce protected type `Generated`",
    ):
        check(
            parse_source("""
def main(access: PythonCall) -> Result[Generated[String], PythonError] ! {Python.Call}:
    return python_call[Generated[String]]("calculator.add", "input", access)
""")
        )
