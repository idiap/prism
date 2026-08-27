# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Canonical effect recording, content-addressed artifacts, and replay verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, cast

from prism.language.core import CoreType, Err
from prism.runtime.effects import EffectRequest, EffectResult

ReplayStatus = Literal["verified", "changed", "unavailable", "failed"]


def jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return jsonable(asdict(cast(Any, value)))
    if isinstance(value, Mapping):
        return {
            str(key): jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, tuple | list):
        return [jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return {"encoding": "hex", "data": value.hex()}
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def content_digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    digest: str
    media_type: str
    size: int


class ArtifactStore(Protocol):
    def put(
        self, value: Any, *, media_type: str = "application/json"
    ) -> ArtifactRef: ...

    def get(self, reference: ArtifactRef | str) -> Any: ...

    def verify(self, reference: ArtifactRef | str) -> bool: ...


class MemoryArtifactStore:
    def __init__(self) -> None:
        self._artifacts: dict[str, bytes] = {}

    def put(self, value: Any, *, media_type: str = "application/json") -> ArtifactRef:
        payload = canonical_bytes(value)
        digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
        self._artifacts[digest] = payload
        return ArtifactRef(digest, media_type, len(payload))

    def get(self, reference: ArtifactRef | str) -> Any:
        digest = reference.digest if isinstance(reference, ArtifactRef) else reference
        return json.loads(self._artifacts[digest].decode("utf-8"))

    def verify(self, reference: ArtifactRef | str) -> bool:
        digest = reference.digest if isinstance(reference, ArtifactRef) else reference
        payload = self._artifacts.get(digest)
        return (
            payload is not None
            and f"sha256:{hashlib.sha256(payload).hexdigest()}" == digest
        )


class FileArtifactStore:
    """File-backed content-addressed JSON artifact store."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, value: Any, *, media_type: str = "application/json") -> ArtifactRef:
        payload = canonical_bytes(value)
        digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
        path = self._path(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(payload)
        return ArtifactRef(digest, media_type, len(payload))

    def get(self, reference: ArtifactRef | str) -> Any:
        digest = reference.digest if isinstance(reference, ArtifactRef) else reference
        return json.loads(self._path(digest).read_text(encoding="utf-8"))

    def verify(self, reference: ArtifactRef | str) -> bool:
        digest = reference.digest if isinstance(reference, ArtifactRef) else reference
        path = self._path(digest)
        if not path.is_file():
            return False
        return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}" == digest

    def _path(self, digest: str) -> Path:
        algorithm, separator, value = digest.partition(":")
        if separator != ":" or algorithm != "sha256" or len(value) != 64:
            raise ValueError(f"invalid artifact digest `{digest}`")
        return self.root / algorithm / value[:2] / f"{value}.json"


@dataclass(frozen=True, slots=True)
class EffectInvocation:
    call_id: str
    symbol: str
    handler: str
    provider_digest: str
    request_artifact: ArtifactRef
    input_artifact: ArtifactRef
    input_digest: str


@dataclass(frozen=True, slots=True)
class EffectObservation:
    status: str
    output_artifact: ArtifactRef
    output_digest: str
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EffectRecord:
    record_id: str
    invocation: EffectInvocation
    observation: EffectObservation
    created_at: str
    replay_artifacts: Mapping[str, ArtifactRef] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReplayReport:
    mode: Literal["offline", "live"]
    status: ReplayStatus
    record_id: str
    comparison_record_id: str | None = None
    diagnostics: tuple[str, ...] = ()


class EffectRecorder:
    def __init__(self, store: ArtifactStore | None = None) -> None:
        self.store = store or MemoryArtifactStore()
        self.records: dict[str, EffectRecord] = {}

    def record(self, request: EffectRequest, result: EffectResult) -> EffectRecord:
        executor = result.executor or "runtime"
        inputs = {
            "positional": request.arguments,
            "named": request.named_arguments,
        }
        request_payload = {
            "call_id": request.call_id,
            "symbol": request.symbol,
            "inputs": inputs,
            "result_type": request.result_type,
            "effects": request.effects,
            "permissions": request.permissions,
            "metadata": request.metadata,
        }
        outputs = {
            "value": result.value,
            "type": result.type,
            "diagnostics": result.diagnostics,
            "provenance": result.provenance,
        }
        input_ref = self.store.put(inputs)
        request_ref = self.store.put(request_payload)
        output_ref = self.store.put(outputs)
        replay_refs = {
            name: self.store.put(value)
            for name, value in sorted(result.replay_artifacts.items())
        }
        provider_digest = content_digest(
            {
                "symbol": request.symbol,
                "executor": executor,
                "effects": request.effects,
            }
        )
        record_payload = {
            "call_id": request.call_id,
            "symbol": request.symbol,
            "handler": executor,
            "provider_digest": provider_digest,
            "request_digest": request_ref.digest,
            "input_digest": input_ref.digest,
            "output_digest": output_ref.digest,
            "replay_artifacts": {name: ref.digest for name, ref in replay_refs.items()},
        }
        record_id = content_digest(record_payload)
        record = EffectRecord(
            record_id=record_id,
            invocation=EffectInvocation(
                request.call_id,
                request.symbol,
                executor,
                provider_digest,
                request_ref,
                input_ref,
                input_ref.digest,
            ),
            observation=EffectObservation(
                "rejected" if isinstance(result.value, Err) else "accepted",
                output_ref,
                output_ref.digest,
                dict(result.provenance),
            ),
            created_at=datetime.now(UTC).isoformat(),
            replay_artifacts=replay_refs,
        )
        self.records[record_id] = record
        return record

    def offline_verify(self, record: EffectRecord) -> ReplayReport:
        references = [
            record.invocation.input_artifact,
            record.invocation.request_artifact,
            record.observation.output_artifact,
            *record.replay_artifacts.values(),
        ]
        invalid = tuple(
            reference.digest
            for reference in references
            if not self.store.verify(reference)
        )
        if invalid:
            return ReplayReport(
                "offline",
                "failed",
                record.record_id,
                diagnostics=(f"invalid artifacts: {', '.join(invalid)}",),
            )
        expected = content_digest(
            {
                "call_id": record.invocation.call_id,
                "symbol": record.invocation.symbol,
                "handler": record.invocation.handler,
                "provider_digest": record.invocation.provider_digest,
                "request_digest": record.invocation.request_artifact.digest,
                "input_digest": record.invocation.input_digest,
                "output_digest": record.observation.output_digest,
                "replay_artifacts": {
                    name: ref.digest for name, ref in record.replay_artifacts.items()
                },
            }
        )
        if expected != record.record_id:
            return ReplayReport(
                "offline",
                "failed",
                record.record_id,
                diagnostics=("effect record digest mismatch",),
            )
        return ReplayReport("offline", "verified", record.record_id)


def effect_record_from_dict(payload: Mapping[str, Any]) -> EffectRecord:
    invocation = payload["invocation"]
    observation = payload["observation"]
    return EffectRecord(
        record_id=str(payload["record_id"]),
        invocation=EffectInvocation(
            call_id=str(invocation["call_id"]),
            symbol=str(invocation["symbol"]),
            handler=str(invocation["handler"]),
            provider_digest=str(invocation["provider_digest"]),
            request_artifact=ArtifactRef(**invocation["request_artifact"]),
            input_artifact=ArtifactRef(**invocation["input_artifact"]),
            input_digest=str(invocation["input_digest"]),
        ),
        observation=EffectObservation(
            status=str(observation["status"]),
            output_artifact=ArtifactRef(**observation["output_artifact"]),
            output_digest=str(observation["output_digest"]),
            provenance=dict(observation.get("provenance", {})),
        ),
        created_at=str(payload["created_at"]),
        replay_artifacts={
            name: ArtifactRef(**value)
            for name, value in payload.get("replay_artifacts", {}).items()
        },
    )


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "<redacted>"
                if any(
                    token in str(key).lower()
                    for token in ("secret", "password", "token", "api_key")
                )
                else _redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, tuple | list):
        return [_redact(item) for item in value]
    return value


class LiveEffectHandler(Protocol):
    def handles(self, symbol: str, effects: tuple[str, ...]) -> bool: ...

    def execute(self, request: EffectRequest) -> EffectResult: ...


class EffectReplayService:
    """Verify recorded effects offline or repeat them through their original handler."""

    def __init__(
        self, recorder: EffectRecorder, *, handler: LiveEffectHandler | None = None
    ) -> None:
        self.recorder = recorder
        self.handler = handler

    def verify(
        self, record: EffectRecord, *, mode: Literal["offline", "live"] = "offline"
    ) -> ReplayReport:
        if mode == "offline":
            return self.recorder.offline_verify(record)
        offline = self.recorder.offline_verify(record)
        if offline.status != "verified":
            return ReplayReport(
                "live", "failed", record.record_id, diagnostics=offline.diagnostics
            )
        if self.handler is None:
            return ReplayReport(
                "live",
                "unavailable",
                record.record_id,
                diagnostics=("no live effect handler configured",),
            )
        try:
            request = effect_request_from_record(record, self.recorder.store)
        except Exception as exc:
            return ReplayReport(
                "live",
                "failed",
                record.record_id,
                diagnostics=(f"could not restore request: {exc}",),
            )
        if not self.handler.handles(request.symbol, request.effects):
            return ReplayReport(
                "live",
                "unavailable",
                record.record_id,
                diagnostics=(f"no handler accepts `{request.symbol}`",),
            )
        try:
            result = self.handler.execute(request)
            comparison = self.recorder.record(request, result)
        except Exception as exc:
            return ReplayReport(
                "live", "failed", record.record_id, diagnostics=(str(exc),)
            )
        status: ReplayStatus = (
            "verified"
            if comparison.observation.output_digest == record.observation.output_digest
            else "changed"
        )
        return ReplayReport("live", status, record.record_id, comparison.record_id)


def effect_request_from_record(
    record: EffectRecord, store: ArtifactStore
) -> EffectRequest:
    payload = store.get(record.invocation.request_artifact)
    result_type = payload["result_type"]
    if isinstance(result_type, Mapping):
        result_type = _core_type_from_dict(result_type)
    inputs = payload.get("inputs", {})
    return EffectRequest(
        call_id=payload["call_id"],
        symbol=payload["symbol"],
        arguments=tuple(inputs.get("positional", ())),
        named_arguments=dict(inputs.get("named", {})),
        result_type=result_type,
        effects=tuple(payload.get("effects", ())),
        permissions=tuple(payload.get("permissions", ())),
        metadata=dict(payload.get("metadata", {})),
    )


def _core_type_from_dict(payload: Mapping[str, Any]) -> CoreType:
    result = payload.get("result")
    return CoreType(
        str(payload["name"]),
        tuple(_core_type_from_dict(item) for item in payload.get("arguments", ())),
        tuple(
            (item[0], _core_type_from_dict(item[1]))
            for item in payload.get("parameters", ())
        ),
        _core_type_from_dict(result) if isinstance(result, Mapping) else None,
        tuple(payload.get("effects", ())),
    )
