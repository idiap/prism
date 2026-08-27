# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""A checked, axiom-free v1 prelude for native data and equality."""

from __future__ import annotations

from functools import lru_cache

from .declarations import check_declaration
from .environment import (
    CheckedModule,
    Declaration,
    Environment,
    RecursorRule,
    RecursorSpec,
)
from .inductives import Constructor, InductiveDefinition, admit_inductive
from .terms import (
    PROP,
    TYPE,
    App,
    Const,
    ConstructorRef,
    InductiveRef,
    Lam,
    Local,
    Pi,
    RecursorRef,
    Term,
    apps,
)


@lru_cache(maxsize=1)
def prelude_environment() -> Environment:
    environment = Environment()
    environment = _admit_bool(environment)
    environment = _admit_nat(environment)
    environment = _admit_eq(environment)
    environment = _admit_prod(environment)
    environment = _admit_sum(environment)
    environment = _admit_list(environment)
    environment = _admit_sigma(environment)
    environment = _admit_nat_functions(environment)
    return environment


@lru_cache(maxsize=1)
def prelude_module() -> CheckedModule:
    environment = prelude_environment()
    from .serialization import module_hash

    content_hash = module_hash("Prism.Prelude", (), environment.declarations)
    return CheckedModule(
        "Prism.Prelude",
        (),
        environment.declarations,
        environment,
        content_hash,
        axiom_dependencies={
            item.name: item.axiom_dependencies for item in environment.declarations
        },
    )


def _admit_bool(environment: Environment) -> Environment:
    boolean = InductiveRef("Bool")
    return admit_inductive(
        environment,
        InductiveDefinition(
            "Bool",
            TYPE,
            (Constructor("Bool.false", boolean), Constructor("Bool.true", boolean)),
        ),
    )


def _admit_nat(environment: Environment) -> Environment:
    nat = InductiveRef("Nat")
    environment = admit_inductive(
        environment,
        InductiveDefinition(
            "Nat",
            TYPE,
            (
                Constructor("Nat.zero", nat),
                Constructor("Nat.succ", Pi("n", nat, nat)),
            ),
        ),
    )
    environment = environment.extend(
        Declaration(
            "Nat.ind",
            _nat_eliminator_type(PROP),
            kind="recursor",
            transparent=False,
            inductive_name="Nat",
            recursor=_nat_recursor_spec(),
        )
    )
    environment = environment.extend(
        Declaration(
            "Nat.rec",
            _nat_eliminator_type(TYPE),
            kind="recursor",
            transparent=False,
            inductive_name="Nat",
            recursor=_nat_recursor_spec(),
        )
    )
    return environment


def _nat_eliminator_type(target_sort: Term) -> Term:
    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    motive = Pi("n", nat, target_sort)
    base = App(Local(0), zero)
    step = Pi(
        "n",
        nat,
        Pi(
            "ih",
            App(Local(2), Local(0)),
            App(Local(3), App(ConstructorRef("Nat.succ"), Local(1))),
        ),
    )
    result = Pi("n", nat, App(Local(3), Local(0)))
    return Pi("motive", motive, Pi("zero", base, Pi("succ", step, result)))


def _nat_recursor_spec() -> RecursorSpec:
    return RecursorSpec(
        3,
        (
            RecursorRule("Nat.zero", 0, 1),
            RecursorRule("Nat.succ", 1, 2, (0,)),
        ),
    )


def _admit_eq(environment: Environment) -> Environment:
    eq_type = Pi("A", TYPE, Pi("left", Local(0), Pi("right", Local(1), PROP)))
    environment = admit_inductive(
        environment,
        InductiveDefinition(
            "Eq",
            eq_type,
            (
                Constructor(
                    "Eq.rfl",
                    Pi(
                        "A",
                        TYPE,
                        Pi(
                            "value",
                            Local(0),
                            apps(InductiveRef("Eq"), Local(1), Local(0), Local(0)),
                        ),
                    ),
                ),
            ),
        ),
    )
    eq_subst_type = _pi_named(
        (),
        "A",
        TYPE,
        lambda cA: _pi_named(
            cA,
            "motive",
            _pi_named(cA, "value", _v(cA, "A"), lambda _cv: PROP),
            lambda cm: _pi_named(
                cm,
                "x",
                _v(cm, "A"),
                lambda cx: _pi_named(
                    cx,
                    "hx",
                    App(_v(cx, "motive"), _v(cx, "x")),
                    lambda chx: _pi_named(
                        chx,
                        "y",
                        _v(chx, "A"),
                        lambda cy: _pi_named(
                            cy,
                            "h",
                            apps(
                                InductiveRef("Eq"),
                                _v(cy, "A"),
                                _v(cy, "x"),
                                _v(cy, "y"),
                            ),
                            lambda ch: App(_v(ch, "motive"), _v(ch, "y")),
                        ),
                    ),
                ),
            ),
        ),
    )
    environment = check_declaration(
        environment,
        Declaration(
            "Eq.subst",
            eq_subst_type,
            kind="recursor",
            transparent=False,
            inductive_name="Eq",
            recursor=RecursorSpec(
                5,
                (RecursorRule("Eq.rfl", 2, 3, field_positions=()),),
            ),
        ),
    )
    return _admit_nat_equality_lemmas(environment)


def _admit_nat_equality_lemmas(environment: Environment) -> Environment:
    nat = InductiveRef("Nat")
    function = Pi("value", nat, nat)

    symm_type = _pi_named(
        (),
        "a",
        nat,
        lambda ca: _pi_named(
            ca,
            "b",
            nat,
            lambda cb: _pi_named(
                cb,
                "h",
                _nat_eq(_v(cb, "a"), _v(cb, "b")),
                lambda ch: _nat_eq(_v(ch, "b"), _v(ch, "a")),
            ),
        ),
    )
    symm_value = _lam_named(
        (),
        "a",
        nat,
        lambda ca: _lam_named(
            ca,
            "b",
            nat,
            lambda cb: _lam_named(
                cb,
                "h",
                _nat_eq(_v(cb, "a"), _v(cb, "b")),
                lambda ch: _eq_subst(
                    _lam_named(
                        ch,
                        "z",
                        nat,
                        lambda cz: _nat_eq(_v(cz, "z"), _v(cz, "a")),
                    ),
                    _v(ch, "a"),
                    _nat_rfl(_v(ch, "a")),
                    _v(ch, "b"),
                    _v(ch, "h"),
                ),
            ),
        ),
    )
    environment = check_declaration(
        environment,
        Declaration("Nat.eq_symm", symm_type, symm_value, "theorem", transparent=False),
    )

    trans_type = _pi_named(
        (),
        "a",
        nat,
        lambda ca: _pi_named(
            ca,
            "b",
            nat,
            lambda cb: _pi_named(
                cb,
                "c",
                nat,
                lambda cc: _pi_named(
                    cc,
                    "hab",
                    _nat_eq(_v(cc, "a"), _v(cc, "b")),
                    lambda chab: _pi_named(
                        chab,
                        "hbc",
                        _nat_eq(_v(chab, "b"), _v(chab, "c")),
                        lambda chbc: _nat_eq(_v(chbc, "a"), _v(chbc, "c")),
                    ),
                ),
            ),
        ),
    )
    trans_value = _lam_named(
        (),
        "a",
        nat,
        lambda ca: _lam_named(
            ca,
            "b",
            nat,
            lambda cb: _lam_named(
                cb,
                "c",
                nat,
                lambda cc: _lam_named(
                    cc,
                    "hab",
                    _nat_eq(_v(cc, "a"), _v(cc, "b")),
                    lambda chab: _lam_named(
                        chab,
                        "hbc",
                        _nat_eq(_v(chab, "b"), _v(chab, "c")),
                        lambda chbc: _eq_subst(
                            _lam_named(
                                chbc,
                                "z",
                                nat,
                                lambda cz: _nat_eq(_v(cz, "a"), _v(cz, "z")),
                            ),
                            _v(chbc, "b"),
                            _v(chbc, "hab"),
                            _v(chbc, "c"),
                            _v(chbc, "hbc"),
                        ),
                    ),
                ),
            ),
        ),
    )
    environment = check_declaration(
        environment,
        Declaration(
            "Nat.eq_trans", trans_type, trans_value, "theorem", transparent=False
        ),
    )

    congr_type = _pi_named(
        (),
        "f",
        function,
        lambda cf: _pi_named(
            cf,
            "a",
            nat,
            lambda ca: _pi_named(
                ca,
                "b",
                nat,
                lambda cb: _pi_named(
                    cb,
                    "h",
                    _nat_eq(_v(cb, "a"), _v(cb, "b")),
                    lambda ch: _nat_eq(
                        App(_v(ch, "f"), _v(ch, "a")),
                        App(_v(ch, "f"), _v(ch, "b")),
                    ),
                ),
            ),
        ),
    )
    congr_value = _lam_named(
        (),
        "f",
        function,
        lambda cf: _lam_named(
            cf,
            "a",
            nat,
            lambda ca: _lam_named(
                ca,
                "b",
                nat,
                lambda cb: _lam_named(
                    cb,
                    "h",
                    _nat_eq(_v(cb, "a"), _v(cb, "b")),
                    lambda ch: _eq_subst(
                        _lam_named(
                            ch,
                            "z",
                            nat,
                            lambda cz: _nat_eq(
                                App(_v(cz, "f"), _v(cz, "a")),
                                App(_v(cz, "f"), _v(cz, "z")),
                            ),
                        ),
                        _v(ch, "a"),
                        _nat_rfl(App(_v(ch, "f"), _v(ch, "a"))),
                        _v(ch, "b"),
                        _v(ch, "h"),
                    ),
                ),
            ),
        ),
    )
    return check_declaration(
        environment,
        Declaration(
            "Nat.eq_congr", congr_type, congr_value, "theorem", transparent=False
        ),
    )


def _admit_prod(environment: Environment) -> Environment:
    prod_type = Pi("A", TYPE, Pi("B", TYPE, TYPE))
    prod_mk = Pi(
        "A",
        TYPE,
        Pi(
            "B",
            TYPE,
            Pi(
                "fst",
                Local(1),
                Pi(
                    "snd",
                    Local(1),
                    apps(InductiveRef("Prod"), Local(3), Local(2)),
                ),
            ),
        ),
    )
    return admit_inductive(
        environment,
        InductiveDefinition("Prod", prod_type, (Constructor("Prod.mk", prod_mk),)),
    )


def _admit_sum(environment: Environment) -> Environment:
    sum_type = Pi("A", TYPE, Pi("B", TYPE, TYPE))
    inl = Pi(
        "A",
        TYPE,
        Pi(
            "B",
            TYPE,
            Pi("value", Local(1), apps(InductiveRef("Sum"), Local(2), Local(1))),
        ),
    )
    inr = Pi(
        "A",
        TYPE,
        Pi(
            "B",
            TYPE,
            Pi("value", Local(0), apps(InductiveRef("Sum"), Local(2), Local(1))),
        ),
    )
    return admit_inductive(
        environment,
        InductiveDefinition(
            "Sum", sum_type, (Constructor("Sum.inl", inl), Constructor("Sum.inr", inr))
        ),
    )


def _admit_list(environment: Environment) -> Environment:
    list_type = Pi("A", TYPE, TYPE)
    nil = Pi("A", TYPE, App(InductiveRef("List"), Local(0)))
    cons = Pi(
        "A",
        TYPE,
        Pi(
            "head",
            Local(0),
            Pi(
                "tail",
                App(InductiveRef("List"), Local(1)),
                App(InductiveRef("List"), Local(2)),
            ),
        ),
    )
    return admit_inductive(
        environment,
        InductiveDefinition(
            "List",
            list_type,
            (Constructor("List.nil", nil), Constructor("List.cons", cons)),
        ),
    )


def _admit_sigma(environment: Environment) -> Environment:
    sigma_type = Pi("A", TYPE, Pi("B", Pi("value", Local(0), TYPE), TYPE))
    sigma_mk = Pi(
        "A",
        TYPE,
        Pi(
            "B",
            Pi("value", Local(0), TYPE),
            Pi(
                "fst",
                Local(1),
                Pi(
                    "snd",
                    App(Local(1), Local(0)),
                    apps(InductiveRef("Sigma"), Local(3), Local(2)),
                ),
            ),
        ),
    )
    return admit_inductive(
        environment,
        InductiveDefinition("Sigma", sigma_type, (Constructor("Sigma.mk", sigma_mk),)),
    )


def _admit_nat_functions(environment: Environment) -> Environment:
    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    succ = ConstructorRef("Nat.succ")
    nat_function = Pi("left", nat, Pi("right", nat, nat))
    motive = Lam("_", nat, nat)

    add_value = Lam(
        "left",
        nat,
        Lam(
            "right",
            nat,
            apps(
                RecursorRef("Nat.rec"),
                motive,
                Local(0),
                Lam("n", nat, Lam("ih", nat, App(succ, Local(0)))),
                Local(1),
            ),
        ),
    )
    environment = check_declaration(
        environment, Declaration("Nat.add", nat_function, add_value)
    )

    mul_value = Lam(
        "left",
        nat,
        Lam(
            "right",
            nat,
            apps(
                RecursorRef("Nat.rec"),
                motive,
                zero,
                Lam(
                    "n",
                    nat,
                    Lam("ih", nat, apps(Const("Nat.add"), Local(2), Local(0))),
                ),
                Local(1),
            ),
        ),
    )
    environment = check_declaration(
        environment, Declaration("Nat.mul", nat_function, mul_value)
    )
    environment = _admit_nat_arithmetic_lemmas(environment)

    odd_value = Lam(
        "n",
        nat,
        App(succ, apps(Const("Nat.add"), Local(0), Local(0))),
    )
    environment = check_declaration(
        environment, Declaration("Nat.odd", Pi("n", nat, nat), odd_value)
    )

    function = Pi("i", nat, nat)
    sum_range_type = Pi("n", nat, Pi("f", function, nat))
    sum_range_value = Lam(
        "n",
        nat,
        Lam(
            "f",
            function,
            apps(
                RecursorRef("Nat.rec"),
                motive,
                zero,
                Lam(
                    "k",
                    nat,
                    Lam(
                        "ih",
                        nat,
                        apps(Const("Nat.add"), Local(0), App(Local(2), Local(1))),
                    ),
                ),
                Local(1),
            ),
        ),
    )
    environment = check_declaration(
        environment,
        Declaration("Nat.sum_range", sum_range_type, sum_range_value),
    )
    return _admit_odd_sum_theorem(environment)


def _admit_nat_arithmetic_lemmas(environment: Environment) -> Environment:
    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    succ_function = Lam("x", nat, _succ(Local(0)))

    add_zero_type = _pi_named(
        (), "n", nat, lambda cn: _nat_eq(_add(_v(cn, "n"), zero), _v(cn, "n"))
    )
    add_zero_value = apps(
        RecursorRef("Nat.ind"),
        _lam_named(
            (),
            "n",
            nat,
            lambda cn: _nat_eq(_add(_v(cn, "n"), zero), _v(cn, "n")),
        ),
        _nat_rfl(zero),
        _lam_named(
            (),
            "n",
            nat,
            lambda cn: _lam_named(
                cn,
                "ih",
                _nat_eq(_add(_v(cn, "n"), zero), _v(cn, "n")),
                lambda cih: _congr(
                    succ_function,
                    _add(_v(cih, "n"), zero),
                    _v(cih, "n"),
                    _v(cih, "ih"),
                ),
            ),
        ),
    )
    environment = check_declaration(
        environment,
        Declaration(
            "Nat.add_zero", add_zero_type, add_zero_value, "theorem", transparent=False
        ),
    )

    add_succ_type = _pi_named(
        (),
        "a",
        nat,
        lambda ca: _pi_named(
            ca,
            "b",
            nat,
            lambda cb: _nat_eq(
                _add(_v(cb, "a"), _succ(_v(cb, "b"))),
                _succ(_add(_v(cb, "a"), _v(cb, "b"))),
            ),
        ),
    )
    add_succ_value = _lam_named(
        (),
        "a",
        nat,
        lambda ca: _lam_named(
            ca,
            "b",
            nat,
            lambda cb: apps(
                RecursorRef("Nat.ind"),
                _lam_named(
                    cb,
                    "x",
                    nat,
                    lambda cx: _nat_eq(
                        _add(_v(cx, "x"), _succ(_v(cx, "b"))),
                        _succ(_add(_v(cx, "x"), _v(cx, "b"))),
                    ),
                ),
                _nat_rfl(_succ(_v(cb, "b"))),
                _lam_named(
                    cb,
                    "x",
                    nat,
                    lambda cx: _lam_named(
                        cx,
                        "ih",
                        _nat_eq(
                            _add(_v(cx, "x"), _succ(_v(cx, "b"))),
                            _succ(_add(_v(cx, "x"), _v(cx, "b"))),
                        ),
                        lambda cih: _congr(
                            succ_function,
                            _add(_v(cih, "x"), _succ(_v(cih, "b"))),
                            _succ(_add(_v(cih, "x"), _v(cih, "b"))),
                            _v(cih, "ih"),
                        ),
                    ),
                ),
                _v(cb, "a"),
            ),
        ),
    )
    environment = check_declaration(
        environment,
        Declaration(
            "Nat.add_succ", add_succ_type, add_succ_value, "theorem", transparent=False
        ),
    )

    environment = _admit_nat_add_assoc(environment)
    environment = _admit_nat_add_comm(environment)
    environment = _admit_nat_add_swap(environment)
    environment = _admit_nat_mul_succ(environment)
    return _admit_nat_square_step(environment)


def _admit_nat_add_assoc(environment: Environment) -> Environment:
    nat = InductiveRef("Nat")
    assoc_type = _pi_named(
        (),
        "a",
        nat,
        lambda ca: _pi_named(
            ca,
            "b",
            nat,
            lambda cb: _pi_named(
                cb,
                "c",
                nat,
                lambda cc: _nat_eq(
                    _add(_add(_v(cc, "a"), _v(cc, "b")), _v(cc, "c")),
                    _add(_v(cc, "a"), _add(_v(cc, "b"), _v(cc, "c"))),
                ),
            ),
        ),
    )
    succ_function = Lam("x", nat, _succ(Local(0)))
    assoc_value = _lam_named(
        (),
        "a",
        nat,
        lambda ca: _lam_named(
            ca,
            "b",
            nat,
            lambda cb: _lam_named(
                cb,
                "c",
                nat,
                lambda cc: apps(
                    RecursorRef("Nat.ind"),
                    _lam_named(
                        cc,
                        "x",
                        nat,
                        lambda cx: _nat_eq(
                            _add(_add(_v(cx, "x"), _v(cx, "b")), _v(cx, "c")),
                            _add(_v(cx, "x"), _add(_v(cx, "b"), _v(cx, "c"))),
                        ),
                    ),
                    _nat_rfl(_add(_v(cc, "b"), _v(cc, "c"))),
                    _lam_named(
                        cc,
                        "x",
                        nat,
                        lambda cx: _lam_named(
                            cx,
                            "ih",
                            _nat_eq(
                                _add(_add(_v(cx, "x"), _v(cx, "b")), _v(cx, "c")),
                                _add(_v(cx, "x"), _add(_v(cx, "b"), _v(cx, "c"))),
                            ),
                            lambda cih: _congr(
                                succ_function,
                                _add(_add(_v(cih, "x"), _v(cih, "b")), _v(cih, "c")),
                                _add(_v(cih, "x"), _add(_v(cih, "b"), _v(cih, "c"))),
                                _v(cih, "ih"),
                            ),
                        ),
                    ),
                    _v(cc, "a"),
                ),
            ),
        ),
    )
    return check_declaration(
        environment,
        Declaration(
            "Nat.add_assoc", assoc_type, assoc_value, "theorem", transparent=False
        ),
    )


def _admit_nat_add_comm(environment: Environment) -> Environment:
    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    comm_type = _pi_named(
        (),
        "a",
        nat,
        lambda ca: _pi_named(
            ca,
            "b",
            nat,
            lambda cb: _nat_eq(
                _add(_v(cb, "a"), _v(cb, "b")),
                _add(_v(cb, "b"), _v(cb, "a")),
            ),
        ),
    )
    succ_function = Lam("x", nat, _succ(Local(0)))
    comm_value = _lam_named(
        (),
        "a",
        nat,
        lambda ca: _lam_named(
            ca,
            "b",
            nat,
            lambda cb: apps(
                RecursorRef("Nat.ind"),
                _lam_named(
                    cb,
                    "x",
                    nat,
                    lambda cx: _nat_eq(
                        _add(_v(cx, "x"), _v(cx, "b")),
                        _add(_v(cx, "b"), _v(cx, "x")),
                    ),
                ),
                _symm(
                    _add(_v(cb, "b"), zero),
                    _v(cb, "b"),
                    apps(Const("Nat.add_zero"), _v(cb, "b")),
                ),
                _lam_named(
                    cb,
                    "x",
                    nat,
                    lambda cx: _lam_named(
                        cx,
                        "ih",
                        _nat_eq(
                            _add(_v(cx, "x"), _v(cx, "b")),
                            _add(_v(cx, "b"), _v(cx, "x")),
                        ),
                        lambda cih: _trans(
                            _succ(_add(_v(cih, "x"), _v(cih, "b"))),
                            _succ(_add(_v(cih, "b"), _v(cih, "x"))),
                            _add(_v(cih, "b"), _succ(_v(cih, "x"))),
                            _congr(
                                succ_function,
                                _add(_v(cih, "x"), _v(cih, "b")),
                                _add(_v(cih, "b"), _v(cih, "x")),
                                _v(cih, "ih"),
                            ),
                            _symm(
                                _add(_v(cih, "b"), _succ(_v(cih, "x"))),
                                _succ(_add(_v(cih, "b"), _v(cih, "x"))),
                                apps(
                                    Const("Nat.add_succ"),
                                    _v(cih, "b"),
                                    _v(cih, "x"),
                                ),
                            ),
                        ),
                    ),
                ),
                _v(cb, "a"),
            ),
        ),
    )
    return check_declaration(
        environment,
        Declaration(
            "Nat.add_comm", comm_type, comm_value, "theorem", transparent=False
        ),
    )


def _admit_nat_add_swap(environment: Environment) -> Environment:
    nat = InductiveRef("Nat")
    swap_type = _pi_named(
        (),
        "a",
        nat,
        lambda ca: _pi_named(
            ca,
            "b",
            nat,
            lambda cb: _pi_named(
                cb,
                "x",
                nat,
                lambda cx: _nat_eq(
                    _add(_v(cx, "a"), _add(_v(cx, "b"), _v(cx, "x"))),
                    _add(_v(cx, "b"), _add(_v(cx, "a"), _v(cx, "x"))),
                ),
            ),
        ),
    )
    swap_value = _lam_named(
        (),
        "a",
        nat,
        lambda ca: _lam_named(
            ca,
            "b",
            nat,
            lambda cb: _lam_named(
                cb,
                "x",
                nat,
                lambda cx: _trans(
                    _add(_v(cx, "a"), _add(_v(cx, "b"), _v(cx, "x"))),
                    _add(_add(_v(cx, "a"), _v(cx, "b")), _v(cx, "x")),
                    _add(_v(cx, "b"), _add(_v(cx, "a"), _v(cx, "x"))),
                    _symm(
                        _add(_add(_v(cx, "a"), _v(cx, "b")), _v(cx, "x")),
                        _add(_v(cx, "a"), _add(_v(cx, "b"), _v(cx, "x"))),
                        apps(
                            Const("Nat.add_assoc"),
                            _v(cx, "a"),
                            _v(cx, "b"),
                            _v(cx, "x"),
                        ),
                    ),
                    _trans(
                        _add(_add(_v(cx, "a"), _v(cx, "b")), _v(cx, "x")),
                        _add(_add(_v(cx, "b"), _v(cx, "a")), _v(cx, "x")),
                        _add(_v(cx, "b"), _add(_v(cx, "a"), _v(cx, "x"))),
                        _congr(
                            _lam_named(
                                cx,
                                "q",
                                nat,
                                lambda cq: _add(_v(cq, "q"), _v(cq, "x")),
                            ),
                            _add(_v(cx, "a"), _v(cx, "b")),
                            _add(_v(cx, "b"), _v(cx, "a")),
                            apps(Const("Nat.add_comm"), _v(cx, "a"), _v(cx, "b")),
                        ),
                        apps(
                            Const("Nat.add_assoc"),
                            _v(cx, "b"),
                            _v(cx, "a"),
                            _v(cx, "x"),
                        ),
                    ),
                ),
            ),
        ),
    )
    return check_declaration(
        environment,
        Declaration(
            "Nat.add_swap", swap_type, swap_value, "theorem", transparent=False
        ),
    )


def _admit_nat_mul_succ(environment: Environment) -> Environment:
    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    succ_function = Lam("q", nat, _succ(Local(0)))
    theorem_type = _pi_named(
        (),
        "a",
        nat,
        lambda ca: _pi_named(
            ca,
            "b",
            nat,
            lambda cb: _nat_eq(
                _mul(_v(cb, "a"), _succ(_v(cb, "b"))),
                _add(_v(cb, "a"), _mul(_v(cb, "a"), _v(cb, "b"))),
            ),
        ),
    )
    theorem_value = _lam_named(
        (),
        "a",
        nat,
        lambda ca: _lam_named(
            ca,
            "b",
            nat,
            lambda cb: apps(
                RecursorRef("Nat.ind"),
                _lam_named(
                    cb,
                    "x",
                    nat,
                    lambda cx: _nat_eq(
                        _mul(_v(cx, "x"), _succ(_v(cx, "b"))),
                        _add(_v(cx, "x"), _mul(_v(cx, "x"), _v(cx, "b"))),
                    ),
                ),
                _nat_rfl(zero),
                _lam_named(
                    cb,
                    "x",
                    nat,
                    lambda cx: _lam_named(
                        cx,
                        "ih",
                        _nat_eq(
                            _mul(_v(cx, "x"), _succ(_v(cx, "b"))),
                            _add(_v(cx, "x"), _mul(_v(cx, "x"), _v(cx, "b"))),
                        ),
                        lambda cih: _congr(
                            succ_function,
                            _add(
                                _v(cih, "b"),
                                _mul(_v(cih, "x"), _succ(_v(cih, "b"))),
                            ),
                            _add(
                                _v(cih, "x"),
                                _add(
                                    _v(cih, "b"),
                                    _mul(_v(cih, "x"), _v(cih, "b")),
                                ),
                            ),
                            _trans(
                                _add(
                                    _v(cih, "b"),
                                    _mul(_v(cih, "x"), _succ(_v(cih, "b"))),
                                ),
                                _add(
                                    _v(cih, "b"),
                                    _add(
                                        _v(cih, "x"),
                                        _mul(_v(cih, "x"), _v(cih, "b")),
                                    ),
                                ),
                                _add(
                                    _v(cih, "x"),
                                    _add(
                                        _v(cih, "b"),
                                        _mul(_v(cih, "x"), _v(cih, "b")),
                                    ),
                                ),
                                _congr(
                                    _lam_named(
                                        cih,
                                        "q",
                                        nat,
                                        lambda cq: _add(_v(cq, "b"), _v(cq, "q")),
                                    ),
                                    _mul(_v(cih, "x"), _succ(_v(cih, "b"))),
                                    _add(
                                        _v(cih, "x"),
                                        _mul(_v(cih, "x"), _v(cih, "b")),
                                    ),
                                    _v(cih, "ih"),
                                ),
                                apps(
                                    Const("Nat.add_swap"),
                                    _v(cih, "b"),
                                    _v(cih, "x"),
                                    _mul(_v(cih, "x"), _v(cih, "b")),
                                ),
                            ),
                        ),
                    ),
                ),
                _v(cb, "a"),
            ),
        ),
    )
    return check_declaration(
        environment,
        Declaration(
            "Nat.mul_succ", theorem_type, theorem_value, "theorem", transparent=False
        ),
    )


def _admit_nat_square_step(environment: Environment) -> Environment:
    nat = InductiveRef("Nat")
    theorem_type = _pi_named(
        (),
        "k",
        nat,
        lambda ck: _nat_eq(
            _add(
                _mul(_v(ck, "k"), _v(ck, "k")),
                _succ(_add(_v(ck, "k"), _v(ck, "k"))),
            ),
            _mul(_succ(_v(ck, "k")), _succ(_v(ck, "k"))),
        ),
    )
    theorem_value = _lam_named(
        (),
        "k",
        nat,
        lambda ck: _trans(
            _add(
                _mul(_v(ck, "k"), _v(ck, "k")),
                _succ(_add(_v(ck, "k"), _v(ck, "k"))),
            ),
            _succ(
                _add(
                    _mul(_v(ck, "k"), _v(ck, "k")),
                    _add(_v(ck, "k"), _v(ck, "k")),
                )
            ),
            _mul(_succ(_v(ck, "k")), _succ(_v(ck, "k"))),
            apps(
                Const("Nat.add_succ"),
                _mul(_v(ck, "k"), _v(ck, "k")),
                _add(_v(ck, "k"), _v(ck, "k")),
            ),
            _trans(
                _succ(
                    _add(
                        _mul(_v(ck, "k"), _v(ck, "k")),
                        _add(_v(ck, "k"), _v(ck, "k")),
                    )
                ),
                _succ(
                    _add(
                        _v(ck, "k"),
                        _add(
                            _v(ck, "k"),
                            _mul(_v(ck, "k"), _v(ck, "k")),
                        ),
                    )
                ),
                _mul(_succ(_v(ck, "k")), _succ(_v(ck, "k"))),
                _congr(
                    Lam("q", nat, _succ(Local(0))),
                    _add(
                        _mul(_v(ck, "k"), _v(ck, "k")),
                        _add(_v(ck, "k"), _v(ck, "k")),
                    ),
                    _add(
                        _v(ck, "k"),
                        _add(
                            _v(ck, "k"),
                            _mul(_v(ck, "k"), _v(ck, "k")),
                        ),
                    ),
                    _trans(
                        _add(
                            _mul(_v(ck, "k"), _v(ck, "k")),
                            _add(_v(ck, "k"), _v(ck, "k")),
                        ),
                        _add(
                            _v(ck, "k"),
                            _add(
                                _mul(_v(ck, "k"), _v(ck, "k")),
                                _v(ck, "k"),
                            ),
                        ),
                        _add(
                            _v(ck, "k"),
                            _add(
                                _v(ck, "k"),
                                _mul(_v(ck, "k"), _v(ck, "k")),
                            ),
                        ),
                        apps(
                            Const("Nat.add_swap"),
                            _mul(_v(ck, "k"), _v(ck, "k")),
                            _v(ck, "k"),
                            _v(ck, "k"),
                        ),
                        _congr(
                            _lam_named(
                                ck,
                                "q",
                                nat,
                                lambda cq: _add(_v(cq, "k"), _v(cq, "q")),
                            ),
                            _add(
                                _mul(_v(ck, "k"), _v(ck, "k")),
                                _v(ck, "k"),
                            ),
                            _add(
                                _v(ck, "k"),
                                _mul(_v(ck, "k"), _v(ck, "k")),
                            ),
                            apps(
                                Const("Nat.add_comm"),
                                _mul(_v(ck, "k"), _v(ck, "k")),
                                _v(ck, "k"),
                            ),
                        ),
                    ),
                ),
                _symm(
                    _mul(_succ(_v(ck, "k")), _succ(_v(ck, "k"))),
                    _succ(
                        _add(
                            _v(ck, "k"),
                            _add(
                                _v(ck, "k"),
                                _mul(_v(ck, "k"), _v(ck, "k")),
                            ),
                        )
                    ),
                    _congr(
                        _lam_named(
                            ck,
                            "q",
                            nat,
                            lambda cq: _succ(_add(_v(cq, "k"), _v(cq, "q"))),
                        ),
                        _mul(_v(ck, "k"), _succ(_v(ck, "k"))),
                        _add(
                            _v(ck, "k"),
                            _mul(_v(ck, "k"), _v(ck, "k")),
                        ),
                        apps(
                            Const("Nat.mul_succ"),
                            _v(ck, "k"),
                            _v(ck, "k"),
                        ),
                    ),
                ),
            ),
        ),
    )
    return check_declaration(
        environment,
        Declaration(
            "Nat.square_step", theorem_type, theorem_value, "theorem", transparent=False
        ),
    )


def _admit_odd_sum_theorem(environment: Environment) -> Environment:
    nat = InductiveRef("Nat")
    zero = ConstructorRef("Nat.zero")
    odd = Const("Nat.odd")
    theorem_type = _pi_named(
        (),
        "n",
        nat,
        lambda cn: _nat_eq(
            apps(Const("Nat.sum_range"), _v(cn, "n"), odd),
            _mul(_v(cn, "n"), _v(cn, "n")),
        ),
    )
    theorem_value = apps(
        RecursorRef("Nat.ind"),
        _lam_named(
            (),
            "n",
            nat,
            lambda cn: _nat_eq(
                apps(Const("Nat.sum_range"), _v(cn, "n"), odd),
                _mul(_v(cn, "n"), _v(cn, "n")),
            ),
        ),
        _nat_rfl(zero),
        _lam_named(
            (),
            "k",
            nat,
            lambda ck: _lam_named(
                ck,
                "ih",
                _nat_eq(
                    apps(Const("Nat.sum_range"), _v(ck, "k"), odd),
                    _mul(_v(ck, "k"), _v(ck, "k")),
                ),
                lambda cih: _trans(
                    _add(
                        apps(Const("Nat.sum_range"), _v(cih, "k"), odd),
                        App(odd, _v(cih, "k")),
                    ),
                    _add(
                        _mul(_v(cih, "k"), _v(cih, "k")),
                        App(odd, _v(cih, "k")),
                    ),
                    _mul(_succ(_v(cih, "k")), _succ(_v(cih, "k"))),
                    _congr(
                        _lam_named(
                            cih,
                            "q",
                            nat,
                            lambda cq: _add(_v(cq, "q"), App(odd, _v(cq, "k"))),
                        ),
                        apps(Const("Nat.sum_range"), _v(cih, "k"), odd),
                        _mul(_v(cih, "k"), _v(cih, "k")),
                        _v(cih, "ih"),
                    ),
                    apps(Const("Nat.square_step"), _v(cih, "k")),
                ),
            ),
        ),
    )
    return check_declaration(
        environment,
        Declaration(
            "Nat.odd_sum_identity",
            theorem_type,
            theorem_value,
            "theorem",
            transparent=False,
        ),
    )


def _v(context: tuple[str, ...], name: str) -> Local:
    for index, candidate in enumerate(reversed(context)):
        if candidate == name:
            return Local(index)
    raise ValueError(f"unknown named local `{name}`")


def _pi_named(context, name, domain, body):
    return Pi(name, domain, body((*context, name)))


def _lam_named(context, name, domain, body):
    return Lam(name, domain, body((*context, name)))


def _nat_eq(left: Term, right: Term) -> Term:
    return apps(InductiveRef("Eq"), InductiveRef("Nat"), left, right)


def _nat_rfl(value: Term) -> Term:
    return apps(ConstructorRef("Eq.rfl"), InductiveRef("Nat"), value)


def _eq_subst(motive: Term, x: Term, hx: Term, y: Term, equality: Term) -> Term:
    return apps(
        RecursorRef("Eq.subst"),
        InductiveRef("Nat"),
        motive,
        x,
        hx,
        y,
        equality,
    )


def _succ(value: Term) -> Term:
    return App(ConstructorRef("Nat.succ"), value)


def _add(left: Term, right: Term) -> Term:
    return apps(Const("Nat.add"), left, right)


def _mul(left: Term, right: Term) -> Term:
    return apps(Const("Nat.mul"), left, right)


def _congr(function: Term, left: Term, right: Term, proof: Term) -> Term:
    return apps(Const("Nat.eq_congr"), function, left, right, proof)


def _symm(left: Term, right: Term, proof: Term) -> Term:
    return apps(Const("Nat.eq_symm"), left, right, proof)


def _trans(left: Term, middle: Term, right: Term, first: Term, second: Term) -> Term:
    return apps(Const("Nat.eq_trans"), left, middle, right, first, second)
