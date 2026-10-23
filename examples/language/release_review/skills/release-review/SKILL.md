---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

name: release-review
description: Review a proposed change against its release policy using the supplied summary and diff.
metadata:
  version: "1.0.0"
---

# Release review

Return a structured `Review` for the supplied `ReviewTask`.

- Inspect `observations.summary` and `observations.diff` for release risks.
- Summarize the relevant changes, risks, and missing evidence in `summary`.
- Use a nonnegative integer `risk`; values above `criteria.maximum_risk` exceed the policy.
- Set `tests_passed` to true only when the supplied observations explicitly report passing tests. Otherwise return false and explain the missing test evidence.
- Treat reported test results as supplied assertions. Do not claim to have executed tests or formally verified the change.
- Leave the final approval decision to the release policy function.
