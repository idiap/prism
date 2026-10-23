<!--
SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>

SPDX-License-Identifier: MIT
-->

# prism-runtime

Fail-closed execution of compiled Prism command IR through typed effect
handlers, including native workflow composition, typed callable-agent
invocation, invocation-scoped built artifacts, strict certificate-producing
proof tactics, and generic read-only knowledge effects.

Optional knowledge dependencies are available through the `yaml` extra
(`prism-runtime[yaml]`, providing PyYAML) and the `neo4j` extra
(`prism-runtime[neo4j]`, providing the Neo4j driver). The base runtime does not
install either extra.
