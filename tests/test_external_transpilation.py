# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json

import pytest
from prism.language import InMemoryModuleLoader, check, parse_source
from prism.transpiler import BuildError, build_hooks_module, build_skill_module


def test_build_open_agent_skill_emits_typed_standalone_module(tmp_path) -> None:
    source = tmp_path / "review"
    source.mkdir()
    (source / "SKILL.md").write_text(
        '---\nname: review\ndescription: Review code\nmetadata:\n  version: "1.2.0"\n---\n\nBe exact.\n',
        encoding="utf-8",
    )
    result = build_skill_module(
        source,
        "contracts.ReviewTask",
        tmp_path / "generated" / "review_skill",
        modules=InMemoryModuleLoader(
            {"contracts": "type ReviewTask:\n    request: String\n"}
        ),
    )
    generated = result.path.read_text(encoding="utf-8")
    assert result.export == "review_skill"
    assert "review_skill: Skill[ReviewTask]" in generated
    assert "skill_artifact[ReviewTask]" in generated
    assert "SKILL.md" not in generated


def test_skill_build_rejects_untyped_scripts(tmp_path) -> None:
    source = tmp_path / "unsafe"
    (source / "scripts").mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: unsafe\ndescription: Unsafe test skill\n---\nRun it.\n"
    )
    (source / "scripts" / "run.py").write_text("print('x')\n")
    with pytest.raises(BuildError, match="untyped or unsupported"):
        build_skill_module(
            source,
            "contracts.Task",
            tmp_path / "skill.prism",
            modules=InMemoryModuleLoader(
                {"contracts": "type Task:\n    request: String\n"}
            ),
        )


@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_build_native_hooks_emits_provider_typed_module(tmp_path, provider) -> None:
    source = tmp_path / f"{provider}.json"
    source.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "check"}],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    result = build_hooks_module(provider, source, tmp_path / f"{provider}_hooks")
    generated = result.path.read_text(encoding="utf-8")
    provider_type = provider.capitalize()
    assert f"Hooks[{provider_type}]" in generated
    assert f"hooks_artifact[{provider_type}]" in generated
    check(parse_source(generated))


def test_hook_build_rejects_unknown_events(tmp_path) -> None:
    source = tmp_path / "hooks.json"
    source.write_text(json.dumps({"hooks": {"Mystery": {"command": "x"}}}))
    with pytest.raises(BuildError, match="unsupported codex hook event"):
        build_hooks_module("codex", source, tmp_path / "hooks.prism")
