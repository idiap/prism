# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
from prism.language.evidence import Evidence, Provenance
from prism.language.kernel import (
    EMPTY_CONTEXT,
    PROP,
    TYPE,
    ZERO,
    App,
    CheckedTerm,
    Const,
    Constructor,
    ConstructorRef,
    Context,
    Declaration,
    InductiveDefinition,
    InductiveRef,
    Kernel,
    KernelError,
    KernelResourceError,
    Lam,
    Let,
    LevelMax,
    LevelSucc,
    LevelVar,
    Local,
    Pi,
    RecursorRef,
    RecursorRule,
    RecursorSpec,
    ReductionBudget,
    Sort,
    admit_inductive,
    apps,
    check_declaration,
    check_module,
    deserialize_module,
    level_from_int,
    level_leq,
    module_hash,
    normalize_level,
    prelude_module,
    serialize_module,
    shift,
    substitute,
    whnf,
)


def test_kernel_checks_native_inhabitants_without_provider_protocols() -> None:
    nat = InductiveRef("Nat")
    identity = Lam("value", nat, Local(0))
    checked = Kernel().check(identity, Pi("value", nat, nat))

    assert checked.axioms == frozenset()
    assert checked.term_hash
    assert checked.type_hash
    assert checked.environment_hash


def test_kernel_rejects_wrong_type_unknown_constants_and_material_evidence() -> None:
    kernel = Kernel()
    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    with pytest.raises(KernelError, match="expected"):
        kernel.check(zero, Pi("value", nat, nat))
    with pytest.raises(KernelError, match="unknown constant"):
        kernel.infer(Const("fabricated.FalseProof"))
    evidence = Evidence("2 + 2 = 4", (Provenance("test", "fixture"),))
    with pytest.raises(KernelError, match="unsupported or unresolved"):
        kernel.check(evidence, nat)  # type: ignore[arg-type]


def test_checked_module_round_trip_rechecks_exact_import_hashes() -> None:
    nat = InductiveRef("Nat")
    module = check_module(
        "Example",
        (prelude_module(),),
        (Declaration("zero", nat, ConstructorRef("Nat.zero")),),
    )
    payload = serialize_module(module)
    restored = deserialize_module(payload, {"Prism.Prelude": prelude_module()})

    assert restored.content_hash == module.content_hash
    assert restored.axioms_for("zero") == frozenset()
    with pytest.raises(KernelError, match="exact import"):
        deserialize_module(payload, {})


def test_native_odd_sum_theorem_is_axiom_free() -> None:
    kernel = Kernel()
    theorem = Const("Nat.odd_sum_identity")
    checked = kernel.check(theorem, kernel.infer(theorem))

    assert checked.axioms == frozenset()


def test_capture_avoiding_shift_and_substitution_under_nested_binders() -> None:
    term = Lam("y", TYPE, App(Local(1), Local(0)))

    assert shift(term, 1) == Lam("y", TYPE, App(Local(2), Local(0)))
    assert substitute(term, Const("replacement")) == Lam(
        "y", TYPE, App(Const("replacement"), Local(0))
    )


def test_beta_delta_iota_and_zeta_reduction() -> None:
    kernel = Kernel()
    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    succ = ConstructorRef("Nat.succ")
    one = App(succ, zero)
    identity = Lam("n", nat, Local(0))
    motive = Lam("_", nat, nat)
    step = Lam("n", nat, Lam("ih", nat, App(succ, Local(0))))

    assert whnf(kernel.environment, EMPTY_CONTEXT, App(identity, one)) == one
    assert whnf(kernel.environment, EMPTY_CONTEXT, Let("n", nat, one, Local(0))) == one
    assert kernel.is_def_eq(
        whnf(
            kernel.environment,
            EMPTY_CONTEXT,
            apps(RecursorRef("Nat.rec"), motive, zero, step, one),
        ),
        one,
    )
    assert kernel.is_def_eq(
        whnf(
            kernel.environment,
            EMPTY_CONTEXT,
            apps(Const("Nat.add"), zero, one),
        ),
        one,
    )


def test_universes_instantiate_and_cumulate_but_do_not_float_free() -> None:
    universe = LevelVar("u")
    polymorphic_identity = Declaration(
        "id",
        Pi("A", Sort(universe), Pi("value", Local(0), Local(1))),
        Lam("A", Sort(universe), Lam("value", Local(0), Local(0))),
        universe_parameters=("u",),
    )
    environment = check_declaration(prelude_module().environment, polymorphic_identity)
    kernel = Kernel(environment)
    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    instantiated = apps(Const("id", (ZERO,)), nat, zero)

    assert kernel.infer(instantiated) == nat
    assert whnf(environment, EMPTY_CONTEXT, instantiated) == zero
    kernel.check(TYPE, Sort(level_from_int(2)))
    with pytest.raises(KernelError, match="expected"):
        kernel.check(Sort(LevelSucc(ZERO)), Sort(LevelSucc(ZERO)))
    with pytest.raises(KernelError, match="undeclared universe"):
        check_declaration(
            environment,
            Declaration("badUniverse", Sort(LevelVar("missing")), kind="axiom"),
        )


def test_universe_normalization_is_associative_commutative_and_ordered() -> None:
    u = LevelVar("u")
    v = LevelVar("v")
    w = LevelVar("w")
    left = LevelMax(LevelMax(u, v), w)
    right = LevelMax(w, LevelMax(v, u))

    assert normalize_level(left) == normalize_level(right)
    assert level_leq(u, LevelSucc(u))
    assert level_leq(LevelMax(u, v), LevelMax(v, u))
    assert not level_leq(LevelSucc(u), u)


def test_proof_irrelevance_does_not_collapse_distinct_propositions() -> None:
    kernel = Kernel()
    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    one = App(ConstructorRef("Nat.succ"), zero)
    proposition = apps(InductiveRef("Eq"), nat, zero, zero)
    other = apps(InductiveRef("Eq"), nat, zero, one)
    context = Context().push("left", proposition).push("right", proposition)

    assert kernel.is_def_eq(Local(0), Local(1), context=context)
    assert not kernel.is_def_eq(proposition, other)


def test_declarations_reject_non_types_effects_partiality_and_propagate_axioms() -> (
    None
):
    environment = prelude_module().environment
    with pytest.raises(KernelError, match="not itself a type"):
        check_declaration(
            environment,
            Declaration("badType", ConstructorRef("Nat.zero"), kind="axiom"),
        )
    with pytest.raises(KernelError, match="effectful"):
        check_declaration(
            environment,
            Declaration("effectful", PROP, kind="axiom", pure=False),
        )
    with pytest.raises(KernelError, match="not total"):
        check_declaration(
            environment,
            Declaration("partial", PROP, kind="axiom", total=False),
        )

    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    proposition = apps(InductiveRef("Eq"), nat, zero, zero)
    module = check_module(
        "Axioms",
        (prelude_module(),),
        (
            Declaration("assumedProof", proposition, kind="axiom", transparent=False),
            Declaration(
                "usesChoice",
                proposition,
                Const("assumedProof"),
                kind="theorem",
                transparent=False,
            ),
        ),
    )
    assert module.axioms_for("usesChoice") == frozenset({"assumedProof"})


def test_inductive_admission_rejects_negative_occurrences_and_bad_results() -> None:
    environment = prelude_module().environment
    bad = InductiveRef("Bad")
    nat = InductiveRef("Nat")
    with pytest.raises(KernelError, match="negative occurrence"):
        admit_inductive(
            environment,
            InductiveDefinition(
                "Bad",
                TYPE,
                (Constructor("Bad.mk", Pi("f", Pi("x", bad, nat), bad)),),
            ),
        )
    family = InductiveRef("Family")
    with pytest.raises(KernelError, match="expected 1"):
        admit_inductive(
            environment,
            InductiveDefinition(
                "Family",
                Pi("A", TYPE, TYPE),
                (Constructor("Family.mk", family),),
            ),
        )


def test_malformed_recursor_metadata_is_rejected() -> None:
    environment = prelude_module().environment
    with pytest.raises(KernelError, match="scrutinee"):
        check_declaration(
            environment,
            Declaration(
                "Nat.badRec",
                Pi("n", InductiveRef("Nat"), InductiveRef("Nat")),
                kind="recursor",
                transparent=False,
                inductive_name="Nat",
                recursor=RecursorSpec(
                    4,
                    (
                        RecursorRule("Nat.zero", 0, 0),
                        RecursorRule("Nat.succ", 1, 0, (0,)),
                    ),
                ),
            ),
        )

    proposition = InductiveRef("PrivateProposition")
    prop_environment = admit_inductive(
        environment,
        InductiveDefinition(
            "PrivateProposition",
            PROP,
            (Constructor("PrivateProposition.intro", proposition),),
        ),
    )
    with pytest.raises(KernelError, match="eliminates Prop into data"):
        check_declaration(
            prop_environment,
            Declaration(
                "PrivateProposition.rec",
                Pi("method", TYPE, Pi("proof", proposition, TYPE)),
                kind="recursor",
                transparent=False,
                inductive_name="PrivateProposition",
                recursor=RecursorSpec(
                    1,
                    (RecursorRule("PrivateProposition.intro", 0, 0),),
                ),
            ),
        )


def test_module_hashes_are_order_independent_and_import_collisions_fail() -> None:
    type_one = Sort(LevelSucc(ZERO))
    first = check_module(
        "First",
        (prelude_module(),),
        (Declaration("first", type_one, TYPE),),
    )
    second = check_module(
        "Second",
        (prelude_module(),),
        (Declaration("second", type_one, TYPE),),
    )
    left = check_module("Combined", (first, second), ())
    right = check_module("Combined", (second, first), ())
    assert left.content_hash == right.content_hash
    assert module_hash("Combined", left.imports, ()) == left.content_hash

    duplicate_first = check_module(
        "DuplicateFirst",
        (prelude_module(),),
        (Declaration("duplicate", type_one, TYPE),),
    )
    duplicate_second = check_module(
        "DuplicateSecond",
        (prelude_module(),),
        (Declaration("duplicate", type_one, TYPE),),
    )
    with pytest.raises(KernelError, match="duplicate imported declaration"):
        check_module("Collision", (duplicate_first, duplicate_second), ())


def test_reduction_budget_exhaustion_and_non_core_inputs_fail_closed() -> None:
    kernel = Kernel()
    term = Local(0)
    for index in range(20):
        term = Let(f"x{index}", TYPE, TYPE, term)
    with pytest.raises(KernelResourceError):
        whnf(kernel.environment, EMPTY_CONTEXT, term, budget=ReductionBudget(2))
    with pytest.raises(KernelError, match="unsupported or unresolved"):
        kernel.check({"kind": "historical-certificate"}, PROP)  # type: ignore[arg-type]
    forged = CheckedTerm(
        ConstructorRef("Nat.zero"),
        InductiveRef("Nat"),
        kernel.environment.hash,
        "forged-term-hash",
        "forged-type-hash",
    )
    with pytest.raises(KernelError, match="identity"):
        kernel.recheck(forged)


def test_module_deserialization_rejects_wrong_hash_and_non_core_terms() -> None:
    module = check_module("Empty", (), ())
    payload = serialize_module(module).replace(module.content_hash.encode(), b"0" * 64)
    with pytest.raises(KernelError, match="hash mismatch"):
        deserialize_module(payload)
    with pytest.raises(KernelError, match="malformed core term"):
        deserialize_module(
            b'{"format":"1","calculus":"prism-core-v1","name":"Bad",'
            b'"imports":[],"declarations":[{"name":"x","kind":"axiom",'
            b'"type":["metavariable",0],"value":null}],"hash":"bad"}'
        )
