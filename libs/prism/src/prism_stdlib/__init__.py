# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Generic reusable PRISM standard-library assets."""

from pathlib import Path
from sysconfig import get_path


def module_root() -> Path:
    installed_root = Path(get_path("data")) / "prism_modules"
    if any(installed_root.rglob("*.prism")):
        return installed_root
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "libs/prism/reasoning").is_dir():
            return candidate
    return installed_root
