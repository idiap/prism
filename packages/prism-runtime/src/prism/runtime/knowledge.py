# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed knowledge-source adapters, normalized evidence, and retrieval effects."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, Literal, Mapping, Protocol, TypeVar

from prism.language.interop import SourceReference
from prism.runtime.replay import content_digest

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class FileSearchQuery:
    text: str = ""
    limit: int = 20
    result_schema: str = "TextRecord"
    query_kind: Literal["file-search"] = "file-search"


@dataclass(frozen=True, slots=True)
class SqlQuery:
    statement: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    result_schema: str = "SqlRow"
    limit: int = 100
    query_kind: Literal["sql"] = "sql"


@dataclass(frozen=True, slots=True)
class GraphQuery:
    statement: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    result_schema: str = "GraphRecord"
    limit: int = 100
    language: Literal["cypher", "sparql"] = "cypher"
    query_kind: Literal["graph"] = "graph"


@dataclass(frozen=True, slots=True)
class KeyLookupQuery:
    key: str
    result_schema: str = "KeyValue"
    query_kind: Literal["key-lookup"] = "key-lookup"


KnowledgeQuery = FileSearchQuery | SqlQuery | GraphQuery | KeyLookupQuery


@dataclass(frozen=True, slots=True)
class EvidenceItem(Generic[T]):
    record_id: str
    value: T
    source_locator: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class EvidenceSet(Generic[T]):
    kb: SourceReference
    query: KnowledgeQuery
    schema_id: str
    adapter_version: str
    source_snapshot: str | None
    items: tuple[EvidenceItem[T], ...]
    result_hash: str
    snapshot: Any | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeTrustProfile:
    allow_offline_snapshot: bool = True


@dataclass(frozen=True, slots=True)
class KnowledgeSourceConfig:
    source_id: str
    adapter_id: str
    locator: str
    schema_id: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)
    trust: KnowledgeTrustProfile = field(default_factory=KnowledgeTrustProfile)


class KnowledgeBaseAdapter(Protocol):
    adapter_id: str
    version: str
    aliases: tuple[str, ...]

    def validate_source(self, source: KnowledgeSourceConfig) -> None: ...

    def describe(self, source: KnowledgeSourceConfig) -> str | None: ...

    def supports(self, query: KnowledgeQuery) -> bool: ...

    def execute(
        self, source: KnowledgeSourceConfig, query: KnowledgeQuery
    ) -> EvidenceSet[Any]: ...

    def verify_snapshot(self, evidence: EvidenceSet[Any]) -> bool: ...


class KnowledgeAdapterRegistry:
    def __init__(self, adapters: tuple[KnowledgeBaseAdapter, ...] = ()) -> None:
        self._adapters: dict[str, KnowledgeBaseAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: KnowledgeBaseAdapter) -> None:
        for adapter_id in (adapter.adapter_id, *adapter.aliases):
            if (
                adapter_id in self._adapters
                and self._adapters[adapter_id] is not adapter
            ):
                raise ValueError(f"duplicate knowledge adapter `{adapter_id}`")
            self._adapters[adapter_id] = adapter

    def resolve(self, adapter_id: str) -> KnowledgeBaseAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise ValueError(f"unknown knowledge adapter `{adapter_id}`") from exc

    def all(self) -> Mapping[str, KnowledgeBaseAdapter]:
        return dict(self._adapters)


class KnowledgeBroker:
    def __init__(
        self,
        registry: KnowledgeAdapterRegistry,
        sources: Mapping[str, KnowledgeSourceConfig] | None = None,
        *,
        project_root: Path | None = None,
    ) -> None:
        self.registry = registry
        self.sources = dict(sources or {})
        self.project_root = (project_root or Path.cwd()).resolve()

    def prepare(self, reference: SourceReference) -> KnowledgeSourceConfig:
        source = self._source(reference)
        adapter = self.registry.resolve(source.adapter_id)
        adapter.validate_source(source)
        actual_schema = adapter.describe(source)
        expected_schema = reference.schema_id or source.schema_id
        if (
            reference.schema_id
            and source.schema_id
            and reference.schema_id != source.schema_id
        ):
            raise ValueError(
                f"knowledge source `{reference.source_id}` declares schema `{source.schema_id}`, "
                f"not `{reference.schema_id}`"
            )
        if expected_schema and actual_schema and expected_schema != actual_schema:
            raise ValueError(
                f"knowledge source `{reference.source_id}` exposes schema `{actual_schema}`, not `{expected_schema}`"
            )
        return source

    def query(
        self, reference: SourceReference, query: KnowledgeQuery
    ) -> EvidenceSet[Any]:
        source = self.prepare(reference)
        adapter = self.registry.resolve(source.adapter_id)
        if not adapter.supports(query):
            raise ValueError(
                f"adapter `{source.adapter_id}` does not support `{query.query_kind}` queries"
            )
        evidence = adapter.execute(source, query)
        expected_schema = reference.schema_id or source.schema_id
        if expected_schema and evidence.schema_id != expected_schema:
            raise ValueError(
                f"query returned schema `{evidence.schema_id}`, expected `{expected_schema}`"
            )
        return evidence

    def verify_snapshot(self, evidence: EvidenceSet[Any]) -> bool:
        source = self._source(evidence.kb)
        if not source.trust.allow_offline_snapshot:
            return False
        return self.registry.resolve(source.adapter_id).verify_snapshot(evidence)

    def _source(self, reference: SourceReference) -> KnowledgeSourceConfig:
        if reference.source_id in self.sources:
            source = self.sources[reference.source_id]
            if reference.adapter_id is not None and reference.adapter_id not in {
                source.adapter_id,
                *self.registry.resolve(source.adapter_id).aliases,
            }:
                raise ValueError(
                    f"knowledge source `{reference.source_id}` uses adapter `{source.adapter_id}`, "
                    f"not `{reference.adapter_id}`"
                )
            return source
        if reference.adapter_id in {
            "file",
            "text",
            "json",
            "yaml",
            "yml",
            "jsonl",
            "graph",
        }:
            return KnowledgeSourceConfig(
                source_id=reference.source_id,
                adapter_id=reference.adapter_id,
                locator=reference.source_id,
                schema_id=reference.schema_id,
                options={"format": reference.adapter_id},
            )
        raise ValueError(f"unknown configured knowledge source `{reference.source_id}`")


class FileKnowledgeAdapter:
    adapter_id = "file"
    version = "1"
    aliases: tuple[str, ...] = ("text", "json", "yaml", "yml", "jsonl", "graph")

    def __init__(self, project_root: Path, *, max_bytes: int = 5_000_000) -> None:
        self.project_root = project_root.resolve()
        self.max_bytes = max_bytes

    def validate_source(self, source: KnowledgeSourceConfig) -> None:
        path = self._path(source)
        if not path.is_file():
            raise ValueError(f"knowledge file not found: `{source.locator}`")
        if path.stat().st_size > self.max_bytes:
            raise ValueError(
                f"knowledge file exceeds {self.max_bytes} bytes: `{source.locator}`"
            )

    def describe(self, source: KnowledgeSourceConfig) -> str | None:
        return source.schema_id

    def supports(self, query: KnowledgeQuery) -> bool:
        return isinstance(query, FileSearchQuery | KeyLookupQuery)

    def execute(
        self, source: KnowledgeSourceConfig, query: KnowledgeQuery
    ) -> EvidenceSet[Any]:
        path = self._path(source)
        payload = path.read_bytes()
        text = payload.decode("utf-8")
        document = self._decode(source, text)
        items = self._items(source, document, query)
        reference = SourceReference(
            source.source_id, source.schema_id, adapter_id=source.adapter_id
        )
        return _evidence_set(
            reference,
            query,
            source.schema_id or getattr(query, "result_schema", "Any"),
            self.version,
            f"sha256:{hashlib.sha256(payload).hexdigest()}",
            items,
            snapshot={"text": text, "format": source.options.get("format")},
        )

    def verify_snapshot(self, evidence: EvidenceSet[Any]) -> bool:
        if not isinstance(evidence.snapshot, Mapping) or not isinstance(
            evidence.snapshot.get("text"), str
        ):
            return False
        source = KnowledgeSourceConfig(
            evidence.kb.source_id,
            "file",
            evidence.kb.source_id,
            evidence.kb.schema_id,
            {"format": evidence.snapshot.get("format")},
        )
        document = self._decode(source, evidence.snapshot["text"])
        items = self._items(source, document, evidence.query)
        replayed = _evidence_set(
            evidence.kb,
            evidence.query,
            evidence.schema_id,
            evidence.adapter_version,
            f"sha256:{hashlib.sha256(evidence.snapshot['text'].encode('utf-8')).hexdigest()}",
            items,
            snapshot=evidence.snapshot,
        )
        return (
            replayed.result_hash == evidence.result_hash
            and replayed.source_snapshot == evidence.source_snapshot
        )

    def _path(self, source: KnowledgeSourceConfig) -> Path:
        relative = Path(source.locator)
        if relative.is_absolute() or "://" in source.locator:
            raise ValueError(
                f"file knowledge locator must be a relative local path: `{source.locator}`"
            )
        path = (self.project_root / relative).resolve()
        if not path.is_relative_to(self.project_root):
            raise ValueError(f"knowledge file escapes project root: `{source.locator}`")
        return path

    def _decode(self, source: KnowledgeSourceConfig, text: str) -> Any:
        format_name = str(
            source.options.get("format")
            or Path(source.locator).suffix.lstrip(".")
            or "text"
        )
        if format_name == "json":
            return json.loads(text)
        if format_name == "jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        if format_name in {"yaml", "yml", "graph"}:
            try:
                import yaml
            except (
                ImportError
            ) as exc:  # pragma: no cover - SDK normally provides PyYAML
                raise ValueError("YAML knowledge files require PyYAML") from exc
            return yaml.safe_load(text)
        return text

    def _items(
        self, source: KnowledgeSourceConfig, document: Any, query: KnowledgeQuery
    ) -> tuple[EvidenceItem[Any], ...]:
        if isinstance(query, KeyLookupQuery):
            if not isinstance(document, Mapping) or query.key not in document:
                return ()
            values = [(query.key, document[query.key])]
        elif isinstance(query, FileSearchQuery):
            candidates = list(
                enumerate(
                    document
                    if isinstance(document, list)
                    else (
                        document.splitlines()
                        if isinstance(document, str)
                        else [document]
                    )
                )
            )
            needle = query.text.casefold().strip()
            values = [
                (str(index), value)
                for index, value in candidates
                if not needle or needle in json.dumps(value, sort_keys=True).casefold()
            ][: query.limit]
        else:  # pragma: no cover - guarded by supports
            raise ValueError(f"unsupported file query `{query}`")
        return tuple(
            _evidence_item(str(record_id), value, f"{source.source_id}#{record_id}")
            for record_id, value in values
        )


class SQLiteKnowledgeAdapter:
    adapter_id = "sqlite"
    version = "1"
    aliases: tuple[str, ...] = ()

    def __init__(self, project_root: Path, *, max_bytes: int = 50_000_000) -> None:
        self.project_root = project_root.resolve()
        self.max_bytes = max_bytes

    def validate_source(self, source: KnowledgeSourceConfig) -> None:
        path = self._path(source)
        if not path.is_file():
            raise ValueError(f"SQLite knowledge source not found: `{source.locator}`")
        if path.stat().st_size > self.max_bytes:
            raise ValueError(f"SQLite knowledge source exceeds {self.max_bytes} bytes")

    def describe(self, source: KnowledgeSourceConfig) -> str | None:
        return source.schema_id

    def supports(self, query: KnowledgeQuery) -> bool:
        return isinstance(query, SqlQuery)

    def execute(
        self, source: KnowledgeSourceConfig, query: KnowledgeQuery
    ) -> EvidenceSet[Any]:
        if not isinstance(query, SqlQuery):
            raise ValueError("SQLite adapter requires SqlQuery")
        _validate_read_only_sql(query.statement)
        path = self._path(source)
        snapshot = path.read_bytes()
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                query.statement, dict(query.parameters)
            ).fetchmany(query.limit + 1)
        finally:
            connection.close()
        if len(rows) > query.limit:
            raise ValueError(f"SQLite query exceeded row limit {query.limit}")
        items = tuple(
            _evidence_item(str(index), dict(row), f"{source.source_id}#row={index}")
            for index, row in enumerate(rows)
        )
        return _evidence_set(
            SourceReference(
                source.source_id, source.schema_id, adapter_id=source.adapter_id
            ),
            query,
            source.schema_id or query.result_schema,
            self.version,
            f"sha256:{hashlib.sha256(snapshot).hexdigest()}",
            items,
            snapshot={"encoding": "hex", "data": snapshot.hex()},
        )

    def verify_snapshot(self, evidence: EvidenceSet[Any]) -> bool:
        if not isinstance(evidence.query, SqlQuery) or not isinstance(
            evidence.snapshot, Mapping
        ):
            return False
        data = evidence.snapshot.get("data")
        if evidence.snapshot.get("encoding") != "hex" or not isinstance(data, str):
            return False
        snapshot = bytes.fromhex(data)
        connection = sqlite3.connect(":memory:")
        try:
            if not hasattr(connection, "deserialize"):
                return False
            connection.deserialize(snapshot)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                evidence.query.statement, dict(evidence.query.parameters)
            ).fetchmany(evidence.query.limit + 1)
        finally:
            connection.close()
        items = tuple(
            _evidence_item(
                str(index), dict(row), f"{evidence.kb.source_id}#row={index}"
            )
            for index, row in enumerate(rows)
        )
        replayed = _evidence_set(
            evidence.kb,
            evidence.query,
            evidence.schema_id,
            evidence.adapter_version,
            f"sha256:{hashlib.sha256(snapshot).hexdigest()}",
            items,
            snapshot=evidence.snapshot,
        )
        return (
            replayed.result_hash == evidence.result_hash
            and replayed.source_snapshot == evidence.source_snapshot
        )

    def _path(self, source: KnowledgeSourceConfig) -> Path:
        relative = Path(source.locator)
        if relative.is_absolute() or "://" in source.locator:
            raise ValueError(
                f"SQLite locator must be a relative local path: `{source.locator}`"
            )
        path = (self.project_root / relative).resolve()
        if not path.is_relative_to(self.project_root):
            raise ValueError(f"SQLite source escapes project root: `{source.locator}`")
        return path


class Neo4jKnowledgeAdapter:
    adapter_id = "neo4j"
    version = "1"
    aliases: tuple[str, ...] = ("cypher",)

    def __init__(self, *, driver_factory: Any | None = None) -> None:
        self.driver_factory = driver_factory

    def validate_source(self, source: KnowledgeSourceConfig) -> None:
        if not source.options.get("uri"):
            raise ValueError(f"Neo4j source `{source.source_id}` must configure `uri`")
        if not source.options.get("user_env") or not source.options.get("password_env"):
            raise ValueError(
                f"Neo4j source `{source.source_id}` must use environment credential references"
            )

    def describe(self, source: KnowledgeSourceConfig) -> str | None:
        return source.schema_id

    def supports(self, query: KnowledgeQuery) -> bool:
        return isinstance(query, GraphQuery) and query.language == "cypher"

    def execute(
        self, source: KnowledgeSourceConfig, query: KnowledgeQuery
    ) -> EvidenceSet[Any]:
        if not isinstance(query, GraphQuery) or query.language != "cypher":
            raise ValueError("Neo4j adapter requires a Cypher GraphQuery")
        _validate_read_only_cypher(query.statement)
        driver = self._driver(source)
        try:
            with driver.session(database=source.options.get("database")) as session:
                result = session.run(query.statement, dict(query.parameters))
                records = []
                for record in result:
                    records.append(
                        record.data() if hasattr(record, "data") else dict(record)
                    )
                    if len(records) > query.limit:
                        raise ValueError(
                            f"Neo4j query exceeded row limit {query.limit}"
                        )
                summary = result.consume() if hasattr(result, "consume") else None
        finally:
            driver.close()
        items = tuple(
            _evidence_item(str(index), record, f"{source.source_id}#record={index}")
            for index, record in enumerate(records)
        )
        snapshot = getattr(summary, "bookmark", None) if summary is not None else None
        return _evidence_set(
            SourceReference(
                source.source_id, source.schema_id, adapter_id=source.adapter_id
            ),
            query,
            source.schema_id or query.result_schema,
            self.version,
            str(snapshot) if snapshot else None,
            items,
            snapshot=None,
        )

    def verify_snapshot(self, evidence: EvidenceSet[Any]) -> bool:
        return False  # Neo4j strict offline support requires an explicit signed authority/export attestation.

    def _driver(self, source: KnowledgeSourceConfig):
        user = os.environ.get(str(source.options["user_env"]))
        password = os.environ.get(str(source.options["password_env"]))
        if not user or not password:
            raise ValueError(
                f"Neo4j credentials are unavailable for `{source.source_id}`"
            )
        if self.driver_factory is not None:
            return self.driver_factory(source.options["uri"], auth=(user, password))
        try:
            from neo4j import GraphDatabase  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise ValueError(
                "Neo4j adapter requires the optional `neo4j` package"
            ) from exc
        return GraphDatabase.driver(source.options["uri"], auth=(user, password))


def default_knowledge_registry(
    project_root: Path, *, neo4j_driver_factory: Any | None = None
) -> KnowledgeAdapterRegistry:
    return KnowledgeAdapterRegistry(
        (
            FileKnowledgeAdapter(project_root),
            SQLiteKnowledgeAdapter(project_root),
            Neo4jKnowledgeAdapter(driver_factory=neo4j_driver_factory),
        )
    )


def _evidence_item(
    record_id: str, value: Any, source_locator: str
) -> EvidenceItem[Any]:
    return EvidenceItem(record_id, value, source_locator, content_digest(value))


def _evidence_set(
    reference: SourceReference,
    query: KnowledgeQuery,
    schema_id: str,
    adapter_version: str,
    source_snapshot: str | None,
    items: tuple[EvidenceItem[Any], ...],
    *,
    snapshot: Any | None,
) -> EvidenceSet[Any]:
    unsigned = {
        "kb": reference,
        "query": query,
        "schema_id": schema_id,
        "adapter_version": adapter_version,
        "source_snapshot": source_snapshot,
        "items": items,
    }
    return EvidenceSet(
        reference,
        query,
        schema_id,
        adapter_version,
        source_snapshot,
        items,
        content_digest(unsigned),
        snapshot,
    )


def _validate_read_only_sql(statement: str) -> None:
    normalized = statement.strip().lower()
    if not normalized.startswith(("select ", "with ")) or ";" in normalized.rstrip(";"):
        raise ValueError(
            "SQL knowledge queries must be one read-only SELECT/CTE statement"
        )
    forbidden = (
        " insert ",
        " update ",
        " delete ",
        " drop ",
        " alter ",
        " create ",
        " attach ",
        " pragma ",
    )
    padded = f" {normalized} "
    if any(token in padded for token in forbidden):
        raise ValueError(
            "SQL knowledge queries cannot contain write or administrative operations"
        )


def _validate_read_only_cypher(statement: str) -> None:
    padded = f" {statement.strip().lower()} "
    forbidden = (
        " create ",
        " merge ",
        " delete ",
        " detach ",
        " set ",
        " remove ",
        " drop ",
    )
    if any(token in padded for token in forbidden):
        raise ValueError("Cypher knowledge queries must be read-only")
