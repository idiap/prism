#!/usr/bin/env bash

# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required to run the Python quality checks" >&2
    exit 127
fi

verification_status=0

if ./check.sh; then
    uv run pre-commit run --all-files --show-diff-on-failure || verification_status=1
else
    verification_status=1
fi

./check-vscode.sh || verification_status=1

exit "$verification_status"
