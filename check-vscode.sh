#!/usr/bin/env bash

# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if ! command -v npm >/dev/null 2>&1; then
    echo "error: npm is required to test the VS Code extensions" >&2
    exit 127
fi

npm test --prefix apps/prism-vscode-syntax
npm ci --prefix apps/prism-vscode-extension
npm test --prefix apps/prism-vscode-extension
