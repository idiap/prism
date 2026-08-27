---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: installation
title: Installation
description: Install the Prism language toolchain from a source checkout.
slug: /installation
---

Prism currently runs from a source checkout. The checkout contains the installed
toolchain. Prism programs can live anywhere else on the machine.

## Requirements

Install these tools first.

- Git
- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)

For the VS Code extensions, you also need Node.js, npm, VS Code 1.89 or newer,
and the `code` command on your `PATH`.

## Install the toolchain

Clone the repository and let uv create the managed Python environment.

```bash
git clone https://github.com/idiap/prism.git
cd prism
uv sync --all-packages
```

Confirm that the CLI starts.

```bash
./.venv/bin/prism --help
```

You should see the `parse`, `check`, `compile`, `run`, and `verify-run`
commands. From inside the checkout, `uv run prism --help` is equivalent.

:::tip Keep programs separate

Keep this checkout as the toolchain installation. Create application projects
outside it and call Prism with the absolute path to `.venv/bin/prism`. This
keeps your program independent from the toolchain repository.

:::

## Use Prism from another project

On macOS or Linux, run the following command.

```bash
/path/to/prism/.venv/bin/prism check main.prism
```

On Windows, use the virtual environment executable under `Scripts`.

```powershell
C:\path\to\prism\.venv\Scripts\prism.exe check main.prism
```

You do not need to activate the virtual environment.

Prism discovers the project root from the nearest `runtime.json` containing a
`workspace` value, or from an enclosing `<project>/.prism` source directory.
This lets the CLI and editor resolve project-local and installed standard
library modules when a `.prism` file is opened or checked by absolute path.
Projects without either marker can set an explicit root:

```bash
PRISM_PROJECT_ROOT=/path/to/project /path/to/prism/.venv/bin/prism check /path/to/project/main.prism
```

## Update an existing checkout

After pulling a new version, synchronize the workspace again.

```bash
git pull
uv sync --all-packages
uv run prism --help
```

## Troubleshooting

### `uv` cannot find Python 3.12

Ask uv to install a compatible interpreter, then repeat the synchronization.

```bash
uv python install 3.12
uv sync --all-packages
```

### VS Code cannot find Prism

Verify that the managed interpreter can import the IDE server.

```bash
./.venv/bin/python -c "import prism.tooling.ide_server"
```

If this succeeds, set both VS Code extensions to that exact Python path. The
editor installation pages show the settings.

## Next step

Continue to the [quick start](./quick-start.md) to check, compile, and run a
complete program.
