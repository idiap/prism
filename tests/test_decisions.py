# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from prism.platform.domain.debts import DebtRecord
from prism.platform.domain.decisions import CriticDecision, Diagnostic
from prism.platform.domain.enums import DebtSeverity, DebtStatus, DecisionKind
from pydantic import ValidationError


def test_diagnostic_confidence_must_be_normalized() -> None:
    diagnostic = Diagnostic(judge_id="critic-1", verdict="repair", confidence=0.75)

    assert diagnostic.confidence == 0.75

    try:
        Diagnostic(judge_id="critic-1", verdict="repair", confidence=1.2)
    except ValidationError as exc:
        assert "confidence must be between 0 and 1" in str(exc)
    else:
        raise AssertionError("Expected diagnostic confidence validation to fail.")


def test_critic_decision_keeps_opened_debts() -> None:
    debt = DebtRecord(
        debt_id="debt_1",
        reason="Need stronger evidence.",
        scope={"kind": "evidence"},
        severity=DebtSeverity.MEDIUM,
        opened_at="2026-03-19T12:00:00+00:00",
        discharge_condition={"kind": "new_artifact"},
        status=DebtStatus.ACTIVE,
    )

    decision = CriticDecision(
        decision_id="decision_1",
        kind=DecisionKind.REPAIR,
        target_ref="artifact_1",
        opened_debts=[debt],
    )

    assert decision.kind is DecisionKind.REPAIR
    assert decision.opened_debts[0].reason == "Need stronger evidence."
