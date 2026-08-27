#!/usr/bin/env bash

# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

echo "Running pytest"
uv run pytest

echo "Running Ruff autoformatter"
uv run ruff format --exit-non-zero-on-format .

echo "Running Ruff lint check"
uv run ruff check .

echo "Running Pyright"
uv run pyright

echo "Running Bandit"
uv run bandit -c pyproject.toml -ll -r packages libs

echo "Running Vulture"
uv run vulture

echo "Running REUSE compliance check"
uv run reuse --no-multiprocessing lint
