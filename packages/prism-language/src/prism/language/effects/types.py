# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed effects, failures, and capabilities."""

from __future__ import annotations

STANDARD_EFFECTS = frozenset(
    {
        "AI.Generate",
        "Clock.Read",
        "Context.Disclose",
        "Data.Read",
        "Data.Write",
        "File.Read",
        "File.Write",
        "MCP.Call",
        "Network.Request",
        "Process.Run",
        "Python.Call",
        "Random.Sample",
        "Tool.Call",
        "Trace.Emit",
    }
)

SUPPORTED_EFFECTS = frozenset(
    {
        "AI.Generate",
        "Clock.Read",
        "Context.Disclose",
        "Data.Read",
        "File.Read",
        "MCP.Call",
        "Network.Request",
        "Process.Run",
        "Python.Call",
        "Tool.Call",
    }
)
