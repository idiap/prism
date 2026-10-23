# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Runtime evidence operations."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from prism.language.core import (
    ComputedValue,
    CoreType,
    Err,
    Ok,
    ValidatedValue,
)
from prism.language.evidence import (
    Assessment,
    Evidence,
    PolicyDecision,
    Provenance,
    Supported,
)
from prism.language.kernel import (
    Term,
)
from prism.runtime.results import TraceEvent

from .provenance import CallReferences
from .values import ClaimValue, PolicyValue, ValidatorValue, _Callable

if TYPE_CHECKING:
    from .execution import _Engine


def _builtin_observe(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    provenance = Provenance(
        str(named.get("source", "program")),
        str(named.get("method", "observation")),
        integrity="Supplied",
    )
    value = args[0]
    evidence = Evidence(value, (provenance,))
    self.trace.append(
        TraceEvent(
            "evidence-created",
            provenance.source,
            provenance="Evidence",
            metadata={"method": provenance.method},
        )
    )
    self.provenance.produce(evidence, "asserted", "observe", source=provenance.source)
    return evidence


def _builtin_map_evidence(
    self: _Engine, args, named, result_type=None, expected_term=None
):
    evidence = args[0]
    context = self.provenance.current_call
    references = (
        (
            self.provenance.project(context.positional[0], "value", evidence.value),
            *context.positional[1:],
        )
        if context is not None
        else ()
    )
    value, identity, digest = _transform(
        self,
        named["transformation"],
        (evidence.value, *args[1:]),
        references=references,
    )
    return _transformed_evidence(self, (evidence,), value, identity, digest)


def _builtin_combine_evidence(
    self: _Engine, args, named, result_type=None, expected_term=None
):
    context = self.provenance.current_call
    references = (
        tuple(
            self.provenance.project(reference, "value", packet.value)
            for reference, packet in zip(context.positional, args, strict=True)
        )
        if context is not None
        else ()
    )
    value, identity, digest = _transform(
        self,
        named["transformation"],
        tuple(packet.value for packet in args),
        references=references,
    )
    return _transformed_evidence(self, args, value, identity, digest)


def _transformed_evidence(self, packets, value, identity, digest):
    evidence = Evidence(
        value,
        tuple(
            replace(item, transformations=(*item.transformations, identity))
            for packet in packets
            for item in packet.provenance
        ),
    )
    self.trace.append(
        TraceEvent(
            "evidence-transformed",
            identity,
            provenance="Evidence",
            metadata={"inputs": len(packets), "implementation_hash": digest},
        )
    )
    context = self.provenance.current_call
    assert context is not None and context.function_result is not None
    self.provenance.produce(
        evidence,
        "computed",
        identity,
        children={"value": context.function_result},
        implementation_hash=digest,
    )
    return evidence


def _builtin_compute(self: _Engine, args, named, result_type=None, expected_term=None):
    value, identity, digest = _transform(self, named["procedure"], args)
    self.trace.append(
        TraceEvent(
            "deterministic-computation",
            identity,
            provenance="Computed",
            metadata={"implementation_hash": digest},
        )
    )
    computed = ComputedValue(value, identity)
    context = self.provenance.current_call
    assert context is not None and context.function_result is not None
    self.provenance.produce(
        computed,
        "computed",
        identity,
        children={"value": context.function_result},
        implementation_hash=digest,
    )
    return computed


def _transform(self, function, args, *, references=None):
    if (
        not isinstance(function, _Callable)
        or function.definition.effects
        or function.definition.result_type.name in {"Result", "Err", "Workflow"}
    ):
        raise ValueError("transformation requires a pure infallible callable")
    definition = function.definition
    parent = self.provenance.current_call
    inputs = (
        references
        if references is not None
        else parent.positional
        if parent is not None
        else ()
    )
    context = CallReferences(inputs)
    self.provenance.calls.append(context)
    try:
        value = self._invoke_function(definition, args, {})
        identity = definition.identity or definition.name
        digest = sha256(repr(definition).encode()).hexdigest()
        reference = context.function_result
    finally:
        self.provenance.calls.pop()
    if parent is not None:
        parent.function_result = reference
    return value, identity, digest


def _builtin_validator(
    self: _Engine, args, named, result_type=None, expected_term=None
):
    check = args[0]
    if not isinstance(check, _Callable) or check.definition.effects:
        raise ValueError("validator requires a pure function")
    if result_type is None or result_type.name != "Validator":
        raise ValueError("validator is missing its checked specification")
    identity = check.definition.identity or check.definition.name
    digest = sha256(repr(check.definition).encode()).hexdigest()
    return ValidatorValue(check, result_type, identity, digest)


def _builtin_validate(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    supplied = args[0]
    validator = named["validator"]
    if not isinstance(validator, ValidatorValue):
        raise ValueError("validate requires a registered validator")
    result = self._call(validator.callable, (supplied,), {}, self.global_env)
    if type(result) is not bool:
        raise ValueError("validator must return Bool")
    if result_type is None or result_type.name != "Result":
        raise ValueError("validation is missing its checked specification")
    proposition = result_type.arguments[0].arguments[1].render()
    self.trace.append(
        TraceEvent(
            "validation",
            validator.identity,
            status="accepted" if result else "rejected",
            assurance="Validated" if result else "Unchecked",
            metadata={
                "specification": proposition,
                "result": result,
                "validator_hash": validator.content_hash,
            },
        )
    )
    if not result:
        return Err("deterministic validator rejected the supplied value")
    return Ok(
        ValidatedValue(
            supplied,
            validator.identity,
            proposition,
            result,
            validator.content_hash,
            named["_claim"],
        )
    )


def _builtin_material_policy(
    self: _Engine, args, named, result_type=None, expected_term=None
):
    evaluator = named["evaluator"]
    claim = named["_claim"]
    if not isinstance(evaluator, _Callable) or not isinstance(claim, ClaimValue):
        raise ValueError(
            "material policy requires a typed evaluator and instantiated claim"
        )
    definition = evaluator.definition
    return PolicyValue(
        str(args[0]),
        evaluator,
        {
            name: value
            for name, value in named.items()
            if name not in {"evaluator", "_claim"}
        },
        claim,
        definition.identity or definition.name,
        sha256(repr(definition).encode()).hexdigest(),
    )


def _builtin_accept_assessment(self, args, named, result_type=None, expected_term=None):
    return PolicyDecision("accepted", args[0])


def _builtin_reject_assessment(self, args, named, result_type=None, expected_term=None):
    return PolicyDecision("rejected", args[0])


def _builtin_inconclusive_assessment(
    self, args, named, result_type=None, expected_term=None
):
    return PolicyDecision("inconclusive", args[0])


def _builtin_accept_support(
    self: _Engine, args, named, result_type=None, expected_term=None
):
    assessment = args[0]
    if not isinstance(assessment, Assessment):
        raise ValueError("accept_support requires an assessment")
    if assessment.disposition != "accepted":
        return Err(assessment)
    return Ok(Supported(assessment))


def _eval_material_inference(
    self: _Engine, expression: Any, env: dict[str, Any]
) -> Any:
    evidence = self._eval(expression.evidence, env)
    evidence_value_reference = self.provenance.last
    policy = self._eval(expression.policy, env)
    policy_reference = self.provenance.last
    claim = self._eval(expression.proposition, env)
    claim_reference = self.provenance.last
    if not isinstance(evidence, Evidence) or not isinstance(policy, PolicyValue):
        raise ValueError("material inference requires evidence and a registered policy")
    if not isinstance(claim, ClaimValue) or claim != policy.claim:
        raise ValueError("policy does not apply to the exact instantiated claim")
    assert (
        evidence_value_reference is not None
        and claim_reference is not None
        and policy_reference is not None
    )
    claim_inputs = dict(self.provenance.values[claim_reference].children)
    operational_inputs = dict(self.provenance.values[policy_reference].children)
    references = CallReferences(
        (
            evidence_value_reference,
            *(
                claim_inputs[f"argument:{index}"]
                for index in range(len(claim.arguments))
            ),
        ),
        {name: operational_inputs[name] for name in policy.operational_inputs},
    )
    result = self._call(
        policy.evaluator,
        (evidence, *claim.arguments),
        policy.operational_inputs,
        env,
        references=references,
    )
    if isinstance(result, Err):
        self.trace.append(
            TraceEvent(
                "material-policy",
                policy.name,
                status="failed",
                metadata={
                    "policy_identity": policy.identity,
                    "policy_hash": policy.content_hash,
                    "error": result.error,
                },
            )
        )
        return result
    decision = result.value if isinstance(result, Ok) else result
    if not isinstance(decision, PolicyDecision):
        raise ValueError("policy evaluator must return a PolicyDecision")
    evidence_reference = self.effect_recorder.store.put(evidence).digest
    assessment = Assessment(
        str(claim),
        evidence,
        policy.name,
        decision,
        policy.identity,
        policy.content_hash,
        claim,
        evidence_reference,
    )
    self.trace.append(
        TraceEvent(
            "material-policy",
            policy.name,
            status=decision.disposition,
            assurance="Unchecked",
            metadata={
                "proposition": str(claim),
                "disposition": decision.disposition,
                "explanation": decision.explanation,
                "policy_identity": policy.identity,
                "policy_hash": policy.content_hash,
                "evidence_reference": evidence_reference,
            },
        )
    )
    inputs = (evidence_value_reference, claim_reference, self.provenance.last)
    assessment_reference = self.provenance.record(
        assessment,
        "computed",
        "policy assessment",
        inputs,
        children={"evidence": evidence_value_reference, "claim": claim_reference},
        implementation_hash=policy.content_hash,
    )
    output = Ok(assessment)
    self.provenance.record(
        output,
        "computed",
        "assessment result",
        (assessment_reference,),
        children={"value": assessment_reference},
    )
    return output
