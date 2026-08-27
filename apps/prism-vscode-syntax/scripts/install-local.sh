#!/usr/bin/env bash

# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXTENSION_DIR="$(dirname -- "$SCRIPT_DIR")"
CODE_COMMAND="${CODE_COMMAND:-code}"

for command_name in node npm npx "$CODE_COMMAND"; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command not found: $command_name" >&2
    exit 1
  fi
done

cd -- "$EXTENSION_DIR"

VERSION="$(node -p "require('./package.json').version")"
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/prism-language-support.XXXXXX")"
VSIX_PATH="$TEMP_DIR/prism-language-support-$VERSION.vsix"

cleanup() {
  rm -f -- "$VSIX_PATH"
  rmdir -- "$TEMP_DIR" 2>/dev/null || true
}
trap cleanup EXIT

echo "Running extension tests..."
npm test

echo "Packaging Prism language support $VERSION..."
npx --yes @vscode/vsce package --out "$VSIX_PATH"

echo "Installing $VSIX_PATH..."
"$CODE_COMMAND" --install-extension "$VSIX_PATH" --force

echo
echo "Installed prism.prism-language-support $VERSION."
echo "Run 'Developer: Reload Window' in VS Code to activate it."
