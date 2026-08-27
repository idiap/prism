# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Source-independent module loading and resolution."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from .declarations import CallableContract, RecordContract


@dataclass(frozen=True, slots=True)
class ModuleSource:
    name: str
    source: str
    origin: str | None = None


class ModuleLoader(Protocol):
    def load_module(self, name: str) -> ModuleSource:
        """Load source without imposing a filesystem layout."""

        ...


@dataclass(frozen=True, slots=True)
class LanguageModule:
    name: str
    callables: Mapping[str, CallableContract]
    records: Mapping[str, RecordContract]
    declarations: Mapping[str, Any]
    source_file: str | None = None
    source_hash: str | None = None


class InMemoryModuleLoader:
    def __init__(self, modules: Mapping[str, str | ModuleSource]) -> None:
        self._modules = dict(modules)

    def load_module(self, name: str) -> ModuleSource:
        try:
            source = self._modules[name]
        except KeyError as exc:
            raise ValueError(f"unknown Prism module `{name}`") from exc
        if isinstance(source, ModuleSource):
            return source
        return ModuleSource(name, source, f"memory:{name}")


class ModuleResolver:
    """Resolve modules using injected parsing and declaration extraction."""

    def __init__(
        self,
        loader: ModuleLoader,
        parser: Callable[[str, str | None], Any],
        extractor: Callable[
            [Any], tuple[Mapping[str, CallableContract], Mapping[str, RecordContract]]
        ],
    ) -> None:
        self.loader = loader
        self.parser = parser
        self.extractor = extractor
        self._cache: dict[str, LanguageModule] = {}

    def resolve_module(self, name: str) -> LanguageModule:
        if name in self._cache:
            return self._cache[name]
        source = self.loader.load_module(name)
        program = self.parser(source.source, source.origin)
        callables, records = self.extractor(program)
        declarations = {
            declaration.name: declaration
            for declaration in program.declarations
            if getattr(declaration, "name", None)
        }
        module = LanguageModule(
            name,
            callables,
            records,
            declarations,
            source.origin,
            hashlib.sha256(source.source.encode()).hexdigest(),
        )
        self._cache[name] = module
        return module

    def resolve_export(self, module_name: str, export_name: str) -> Any:
        module = self.resolve_module(module_name)
        try:
            return module.declarations[export_name]
        except KeyError as exc:
            choices = ", ".join(sorted(module.declarations))
            raise ValueError(
                f"module `{module_name}` has no export `{export_name}`; available: {choices}"
            ) from exc
