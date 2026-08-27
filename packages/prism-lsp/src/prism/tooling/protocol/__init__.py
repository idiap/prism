# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Wire models shared by Prism language-server and workbench tooling."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PrismIdeDiagnostic(BaseModel):
    """One syntax/type diagnostic for a `.prism` document."""

    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["error", "warning", "info"] = "error"
    message: str
    line: int | None = None
    character: int | None = None
    end_line: int | None = None
    end_character: int | None = None
    line_text: str = ""


class PrismIdeSymbolSpan(BaseModel):
    """Zero-based symbol span for editor consumers."""

    model_config = ConfigDict(extra="forbid")

    line: int
    character: int
    end_line: int | None = None
    end_character: int | None = None


class PrismIdeSymbol(BaseModel):
    """Resolved symbol or syntax item for hover and navigation providers."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: str
    span: PrismIdeSymbolSpan
    detail: str = ""
    module_path: str | None = None
    definition_path: str | None = None
    source_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PrismIdeTypeSpan(BaseModel):
    """Compiler-derived type for one source expression or declaration."""

    model_config = ConfigDict(extra="forbid")

    span: PrismIdeSymbolSpan
    type_text: str
    kind: str
    name: str | None = None


class PrismIdeDefinitionTarget(BaseModel):
    """One canonical source target for editor definition navigation."""

    model_config = ConfigDict(extra="forbid")

    definition_path: str
    span: PrismIdeSymbolSpan


class PrismIdeDefinitionResult(BaseModel):
    """Compiler-resolved origin and targets for one document position."""

    model_config = ConfigDict(extra="forbid")

    origin: PrismIdeSymbolSpan
    targets: list[PrismIdeDefinitionTarget] = Field(default_factory=list)


class PrismIdeSemanticToken(BaseModel):
    """One compiler-classified semantic token for editor highlighting."""

    model_config = ConfigDict(extra="forbid")

    span: PrismIdeSymbolSpan
    token_type: Literal[
        "keyword",
        "function",
        "type",
        "parameter",
        "variable",
        "property",
        "label",
        "operator",
    ]
    modifiers: list[str] = Field(default_factory=list)


class PrismIdeCompletionItem(BaseModel):
    """One type-directed source completion."""

    model_config = ConfigDict(extra="forbid")

    label: str
    kind: Literal["field", "variant"]
    detail: str = ""
    type_text: str = ""


class PrismIdeCheckResult(BaseModel):
    """Result of real-time parse/type checking."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["valid", "invalid"]
    document_path: str
    diagnostics: list[PrismIdeDiagnostic] = Field(default_factory=list)
    symbols: list[PrismIdeSymbol] = Field(default_factory=list)
    type_spans: list[PrismIdeTypeSpan] = Field(default_factory=list)
    semantic_tokens: list[PrismIdeSemanticToken] = Field(default_factory=list)
    core_module: dict[str, Any] | None = None


class PrismIdeRunResult(BaseModel):
    """Result shown after running a `.prism` document."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "failed"]
    backend: Literal["fake", "litellm"]
    model: str | None = None
    document_path: str
    message: str = ""
    diagnostics: list[PrismIdeDiagnostic] = Field(default_factory=list)
    output: dict[str, Any] | None = None
    run_id: str | None = None
    run_path: str | None = None
    run_created_at: str | None = None


class PrismIdeHealthResponse(BaseModel):
    """Backend health response."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
