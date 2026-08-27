<!--
SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>

SPDX-License-Identifier: MIT
-->

# prism-adapter-python

Effect handler for typed `Python.Call` effects dispatched through
`python_call[Output](operation, input, permission)`. Logical operation names are
bound to Python callables through the `prism.python_effects` entry-point group.
