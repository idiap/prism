# SPDX-FileCopyrightText: Copyright © 2026 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-FileContributor: Andre Freitas andre.freitas@idiap.ch
# Neuro-symbolic AI Group
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

from to_prism.dependencies import (
    BundledArtifact,
    DependencyManifest,
    artifact_manifest,
    bundle_prebuilt_dependencies,
    required_roots,
    resolve_workspace_closure,
    validate_dependency_bundle,
    workspace_distributions,
    write_dependency_lock,
)

REPOSITORY = Path(__file__).resolve().parents[3]


def test_workspace_dependency_closure_contains_public_runtime() -> None:
    distributions = workspace_distributions(REPOSITORY)
    closure, external = resolve_workspace_closure(
        distributions,
        required_roots(handler="codex"),
    )

    names = {item.name for item in closure}
    assert {
        "prism-language",
        "prism-runtime",
        "prism-sdk",
        "prism-cli",
        "prism-transpiler",
        "prism-adapter-codex",
        "prism-adapter-python",
        "prism-stdlib",
    } <= names
    assert any(requirement.lower().startswith("pyyaml") for requirement in external)


def test_dependency_bundle_detects_tampering(tmp_path: Path) -> None:
    wheels = tmp_path / "vendor" / "wheels"
    wheels.mkdir(parents=True)
    wheel = wheels / "prism_language-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    distributions = workspace_distributions(REPOSITORY)
    selected = (distributions["prism-language"],)
    artifacts = artifact_manifest(wheels, selected)
    manifest = {
        "schema_version": 1,
        "distributions": [
            {
                "name": "prism-language",
                "version": "1.0.0",
                "source": "packages/prism-language",
                "requirements": [],
            }
        ],
        "external_requirements": [],
        "artifacts": [
            {
                "filename": artifacts[0].filename,
                "sha256": artifacts[0].sha256,
                "size": artifacts[0].size,
                "distribution": artifacts[0].distribution,
                "version": artifacts[0].version,
            }
        ],
    }
    (tmp_path / "vendor" / "manifest.json").write_text(json.dumps(manifest))
    assert validate_dependency_bundle(tmp_path, require_all_external=False) == []

    wheel.write_bytes(b"tampered")
    assert validate_dependency_bundle(tmp_path, require_all_external=False) == [
        "artifact hash mismatch: prism_language-1.0.0-py3-none-any.whl"
    ]


def test_dependency_lock_pins_every_bundled_wheel(tmp_path: Path) -> None:
    manifest = DependencyManifest(
        schema_version=1,
        python="3.12",
        platform="test",
        roots=("prism-cli",),
        distributions=(),
        external_requirements=("PyYAML>=6",),
        artifacts=(
            BundledArtifact(
                "prism_cli-1.0.0-py3-none-any.whl",
                "a" * 64,
                1,
                "prism-cli",
                "1.0.0",
                "unknown",
            ),
            BundledArtifact(
                "PyYAML-6.0.2-py3-none-any.whl",
                "b" * 64,
                1,
                "PyYAML",
                "6.0.2",
                "MIT",
            ),
        ),
    )
    write_dependency_lock(tmp_path, manifest)

    lock = (tmp_path / "dependency.lock").read_text()
    assert "prism-cli==1.0.0 --hash=sha256:" in lock
    assert "PyYAML==6.0.2 --hash=sha256:" in lock


def test_prebuilt_bundle_keeps_toolkit_out_of_generated_project(
    tmp_path: Path,
) -> None:
    prebuilt = tmp_path / "prebuilt"
    wheels = prebuilt / "wheels"
    wheels.mkdir(parents=True)
    (wheels / "prism_cli-1.0.0-py3-none-any.whl").write_bytes(b"prism")
    (wheels / "to_prism-0.1.0-py3-none-any.whl").write_bytes(b"toolkit")
    manifest = {
        "schema_version": 1,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "platform": f"{sys.platform}-{platform.machine()}",
        "roots": ["prism-cli", "to-prism"],
        "distributions": [
            {
                "name": "prism-cli",
                "version": "1.0.0",
                "source": "packages/prism-cli",
                "requirements": [],
            },
            {
                "name": "to-prism",
                "version": "0.1.0",
                "source": "bundled-toolkit",
                "requirements": [],
            },
        ],
        "external_requirements": [],
        "artifacts": [],
    }
    (prebuilt / "manifest.json").write_text(json.dumps(manifest))

    project = tmp_path / "generated"
    bundled = bundle_prebuilt_dependencies(
        prebuilt_vendor=prebuilt,
        project_root=project,
    )

    assert [item.name for item in bundled.distributions] == ["prism-cli"]
    assert bundled.roots == ("prism-cli",)
    assert sorted(path.name for path in (project / "vendor" / "wheels").iterdir()) == [
        "prism_cli-1.0.0-py3-none-any.whl"
    ]
