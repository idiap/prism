---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: refinement-loop
title: Build a lunar landing refinement loop
description: Build a complete Prism refinement loop with deterministic simulation, typed reasoning, material support, and validation.
slug: /tutorials/refinement-loop
---

Build a lunar landing planner that proposes burn controls, checks the resulting
trajectory, and feeds a counterexample into the next proposal. The finished
application returns a plan accepted by a deterministic simulator.

The program develops one typed layer at a time.

```text
mission and initial plan
    -> abductive candidate
    -> deductive simulation
    -> counterexample and deterministic revision
    -> repeat until accepted or ten iterations complete
    -> validated safe plan
```

Along the way, the program introduces records, propositions, provenance,
assurance, reasoning declarations, relations, agents, skills, bounded
repetition, materialization, effects, permissions, and `solve`.

## Before you begin

Complete [installation](../installation.md) and the
[quick start](../quick-start.md). Run every command from the root of the Prism
checkout.

The finished [refinement loop sources](https://github.com/idiap/prism/-/tree/main/examples/language/refinement_loop)
already live in `examples/language/refinement_loop`. Use a disposable checkout
to replace those files in the order shown here, or read each listing beside the
completed file. The SPDX headers are omitted from the Prism listings to keep
attention on the program.

Create the directory for the program and its skill.

```bash
mkdir -p examples/language/refinement_loop/skills/lunar-refinement-narrator
```

The final layout separates each responsibility.

```text
refinement_loop/
├── types.prism
├── simulation.prism
├── optimization.prism
├── reasoning.prism
├── refinement.prism
├── materialization.prism
├── lunar_refinement_skill.prism
├── main.prism
└── skills/
    └── lunar-refinement-narrator/
        └── SKILL.md
```

## Establish the result contract

Start with the value that the application must return.

```prism
Validated[
    value: Computed[PlanHypothesis],
    SafeUnderModel(value),
]
```

The nested type records two independent facts. `Computed[PlanHypothesis]`
records that a named deterministic procedure assembled the plan.
`Validated[..., SafeUnderModel(value)]` records that a named validator
accepted that exact computed value.

The remaining contract follows from this result.

| Contract part | Choice |
| --- | --- |
| Variable input | A mission and an initial plan |
| Reasoning source | An accepted mission plus evidence for the current plan |
| Candidate operation | Abduction |
| Assessment operation | Deduction through deterministic simulation |
| Loop feedback | A counterexample with observed constraint values |
| Recoverable failures | Model generation or validation failure |
| Effects | Model generation and context disclosure |
| Termination | Acceptance or a static bound of ten iterations |

This contract keeps reasoning strategy, provenance, and assurance independent.
Those three dimensions should remain visible in every later type.

## Define the domain and epistemic types

Create `types.prism`. The records describe the mission, four burns, simulated
trajectory bounds, individual constraint results, and the state carried through
the loop. The abstract propositions name the claims that later validators and
relations establish.

```prism title="types.prism"
from prism.reasoning.methods.abductive import AbductionInput

type Burn:
    duration_seconds: Float
    throttle: Float
    angle_degrees: Float

type MissionConstraints:
    description: String
    initial_x: Float
    initial_altitude: Float
    initial_vx: Float
    initial_vy: Float
    dry_mass: Float
    initial_fuel: Float
    lunar_gravity: Float
    fuel_burn_rate: Float
    fuel_reserve: Float
    max_thrust: Float
    landing_zone_min_x: Float
    landing_zone_max_x: Float
    max_horizontal_speed: Float
    min_vertical_speed: Float
    max_lander_angle: Float
    touchdown_altitude_tolerance: Float

type TrajectoryBounds:
    touchdown_x: Float
    touchdown_altitude: Float
    touchdown_vx: Float
    touchdown_vy: Float
    touchdown_angle: Float
    fuel_remaining: Float
    preterminal_clearance_lower_bound: Float
    terminal_entry_vy_upper_bound: Float
    peak_thrust_upper_bound: Float

type LanderState:
    x: Float
    altitude: Float
    vx: Float
    vy: Float
    fuel: Float

type ConstraintChecks:
    inside_landing_zone: Bool
    horizontal_speed_safe: Bool
    vertical_speed_safe: Bool
    touchdown_altitude_safe: Bool
    attitude_safe: Bool
    fuel_reserve_safe: Bool
    terrain_clearance_safe: Bool
    engine_limit_safe: Bool
    fuel_nonnegative: Bool

type ConstraintResult:
    constraint: String
    satisfied: Bool
    observed_value: Float
    required_condition: String

type Counterexample:
    active: Bool
    assessment_time: Float
    constraints: List[ConstraintResult]

type PlanNarrative:
    strategy: String

type PlanHypothesis:
    mission: MissionConstraints
    strategy: String
    simulator_feedback: Counterexample
    prior_touchdown_x: Float
    prior_touchdown_altitude: Float
    prior_horizontal_speed: Float
    prior_vertical_speed: Float
    prior_lander_angle: Float
    prior_fuel_remaining: Float
    coast: Burn
    braking: Burn
    descent: Burn
    terminal: Burn

type ExplainRefinement:
    mission: MissionConstraints
    feedback: Counterexample
    proposed_plan: PlanHypothesis

def MissionAccepted(mission: MissionConstraints) -> Prop

def PlanWellFormed(plan: Computed[PlanHypothesis]) -> Prop

def PlausiblyExplainsFeedback(
    mission: MissionConstraints,
    hypothesis: Computed[PlanHypothesis],
    prior: PlanHypothesis,
) -> Prop

def SafeUnderModel(plan: Computed[PlanHypothesis]) -> Prop

type AcceptedMission = Validated[
    value: MissionConstraints,
    MissionAccepted(value),
]

type AcceptedPlan = Validated[
    value: Computed[PlanHypothesis],
    PlanWellFormed(value),
]

type LandingAssessment:
    plan: AcceptedPlan
    trajectory: Computed[TrajectoryBounds]
    checks: Computed[ConstraintChecks]
    accepted: Bool
    counterexample: Counterexample

type LunarSource = AbductionInput[
    AcceptedMission,
    Evidence[PlanHypothesis],
]

type TrajectoryRefinementState:
    candidate: AcceptedPlan
    finding: LandingAssessment
    source: LunarSource

type RefineTrajectory = (TrajectoryRefinementState) -> LunarSource

type LunarLandingError:
    | ModelFailure
    | ValidationError
```

Several aliases make the later topology readable.

- `AcceptedMission` is a mission accepted by a deterministic validator.
- `AcceptedPlan` retains both deterministic provenance and plan validation.
- `LunarSource` gives abduction an accepted background plus observed plan
  evidence.
- `RefineTrajectory` describes the pure state transition required by the
  reasoning declaration.
- `LunarLandingError` closes the recoverable failure surface.

The mission and plan remain separate values. This separation prevents the
generated narrative from changing mission constraints.

## Add deterministic simulation

Create `simulation.prism`. Its pure functions advance the lander, simulate
four burns, evaluate the mission constraints, and record a counterexample.

<details>
<summary>Show the complete simulator</summary>

```prism title="simulation.prism"
import examples.language.refinement_loop.types as types
from prism.reasoning.methods.deductive import DeductionInput

def advance_state(
    state: types.LanderState,
    burn: types.Burn,
    mission: types.MissionConstraints,
) -> types.LanderState:
    duration = burn.duration_seconds
    mass = mission.dry_mass + state.fuel
    thrust_acceleration = mission.max_thrust / mass * burn.throttle
    lateral_fraction = burn.angle_degrees / 90.0
    ax = thrust_acceleration * lateral_fraction
    ay = (
        thrust_acceleration * (1.0 - lateral_fraction)
        - mission.lunar_gravity
    )
    return types.LanderState(
        x = state.x + state.vx * duration + 0.5 * ax * duration * duration,
        altitude = (
            state.altitude
            + state.vy * duration
            + 0.5 * ay * duration * duration
        ),
        vx = state.vx + ax * duration,
        vy = state.vy + ay * duration,
        fuel = state.fuel - duration * burn.throttle * mission.fuel_burn_rate,
    )

def simulate_trajectory(
    plan: types.PlanHypothesis,
) -> Computed[types.TrajectoryBounds]:
    mission = plan.mission
    initial = types.LanderState(
        x = mission.initial_x,
        altitude = mission.initial_altitude,
        vx = mission.initial_vx,
        vy = mission.initial_vy,
        fuel = mission.initial_fuel,
    )
    after_coast = advance_state(initial, plan.coast, mission)
    after_braking = advance_state(after_coast, plan.braking, mission)
    before_terminal = advance_state(after_braking, plan.descent, mission)
    touchdown = advance_state(before_terminal, plan.terminal, mission)
    trajectory = types.TrajectoryBounds(
        touchdown_x = touchdown.x,
        touchdown_altitude = touchdown.altitude,
        touchdown_vx = touchdown.vx,
        touchdown_vy = touchdown.vy,
        touchdown_angle = plan.terminal.angle_degrees,
        fuel_remaining = touchdown.fuel,
        preterminal_clearance_lower_bound = before_terminal.altitude,
        terminal_entry_vy_upper_bound = before_terminal.vy,
        peak_thrust_upper_bound = mission.max_thrust,
    )
    return compute(trajectory, procedure = "lunar-trajectory-integrator-v1")

def check_constraints(
    trajectory: Computed[types.TrajectoryBounds],
    mission: types.MissionConstraints,
) -> Computed[types.ConstraintChecks]:
    bounds = trajectory.value
    checks = types.ConstraintChecks(
        inside_landing_zone = (
            bounds.touchdown_x >= mission.landing_zone_min_x
            and bounds.touchdown_x <= mission.landing_zone_max_x
        ),
        horizontal_speed_safe = (
            bounds.touchdown_vx > -mission.max_horizontal_speed
            and bounds.touchdown_vx < mission.max_horizontal_speed
        ),
        vertical_speed_safe = bounds.touchdown_vy > mission.min_vertical_speed,
        touchdown_altitude_safe = (
            bounds.touchdown_altitude >= 0.0
            and bounds.touchdown_altitude < mission.touchdown_altitude_tolerance
        ),
        attitude_safe = bounds.touchdown_angle < mission.max_lander_angle,
        fuel_reserve_safe = bounds.fuel_remaining > mission.fuel_reserve,
        terrain_clearance_safe = (
            bounds.preterminal_clearance_lower_bound > 0.0
            and bounds.terminal_entry_vy_upper_bound < 0.0
            and bounds.touchdown_vy < 0.0
        ),
        engine_limit_safe = bounds.peak_thrust_upper_bound <= mission.max_thrust,
        fuel_nonnegative = bounds.fuel_remaining >= 0.0,
    )
    return compute(checks, procedure = "lunar-constraint-checker-v1")

def build_landing_assessment(
    plan: types.AcceptedPlan,
    trajectory: Computed[types.TrajectoryBounds],
    checks: Computed[types.ConstraintChecks],
) -> types.LandingAssessment:
    hypothesis = plan.value.value
    bounds = trajectory.value
    constraint_checks = checks.value
    accepted = (
        constraint_checks.inside_landing_zone
        and constraint_checks.horizontal_speed_safe
        and constraint_checks.vertical_speed_safe
        and constraint_checks.touchdown_altitude_safe
        and constraint_checks.attitude_safe
        and constraint_checks.fuel_reserve_safe
        and constraint_checks.terrain_clearance_safe
        and constraint_checks.engine_limit_safe
        and constraint_checks.fuel_nonnegative
    )
    return types.LandingAssessment(
        plan = plan,
        trajectory = trajectory,
        checks = checks,
        accepted = accepted,
        counterexample = types.Counterexample(
            active = not accepted,
            assessment_time = (
                hypothesis.coast.duration_seconds
                + hypothesis.braking.duration_seconds
                + hypothesis.descent.duration_seconds
                + hypothesis.terminal.duration_seconds
            ),
            constraints = [
                types.ConstraintResult(
                    constraint = "landing-zone",
                    satisfied = constraint_checks.inside_landing_zone,
                    observed_value = bounds.touchdown_x,
                    required_condition = "configured minimum x <= touchdown x <= configured maximum x",
                ),
                types.ConstraintResult(
                    constraint = "horizontal-speed",
                    satisfied = constraint_checks.horizontal_speed_safe,
                    observed_value = bounds.touchdown_vx,
                    required_condition = "absolute touchdown horizontal speed below the configured maximum",
                ),
                types.ConstraintResult(
                    constraint = "vertical-speed",
                    satisfied = constraint_checks.vertical_speed_safe,
                    observed_value = bounds.touchdown_vy,
                    required_condition = "touchdown vertical speed above the configured minimum",
                ),
                types.ConstraintResult(
                    constraint = "touchdown-altitude",
                    satisfied = constraint_checks.touchdown_altitude_safe,
                    observed_value = bounds.touchdown_altitude,
                    required_condition = "0 <= touchdown altitude < configured tolerance",
                ),
                types.ConstraintResult(
                    constraint = "attitude",
                    satisfied = constraint_checks.attitude_safe,
                    observed_value = bounds.touchdown_angle,
                    required_condition = "touchdown angle below the configured maximum",
                ),
                types.ConstraintResult(
                    constraint = "fuel-reserve",
                    satisfied = constraint_checks.fuel_reserve_safe,
                    observed_value = bounds.fuel_remaining,
                    required_condition = "remaining fuel above the configured reserve",
                ),
                types.ConstraintResult(
                    constraint = "preterminal-clearance",
                    satisfied = bounds.preterminal_clearance_lower_bound > 0.0,
                    observed_value = bounds.preterminal_clearance_lower_bound,
                    required_condition = "preterminal clearance above zero",
                ),
                types.ConstraintResult(
                    constraint = "terminal-entry-descent",
                    satisfied = bounds.terminal_entry_vy_upper_bound < 0.0,
                    observed_value = bounds.terminal_entry_vy_upper_bound,
                    required_condition = "terminal entry vertical speed below zero",
                ),
                types.ConstraintResult(
                    constraint = "touchdown-descent",
                    satisfied = bounds.touchdown_vy < 0.0,
                    observed_value = bounds.touchdown_vy,
                    required_condition = "touchdown vertical speed below zero",
                ),
                types.ConstraintResult(
                    constraint = "engine-limit",
                    satisfied = constraint_checks.engine_limit_safe,
                    observed_value = bounds.peak_thrust_upper_bound,
                    required_condition = "peak thrust at or below the configured maximum",
                ),
                types.ConstraintResult(
                    constraint = "fuel-nonnegative",
                    satisfied = constraint_checks.fuel_nonnegative,
                    observed_value = bounds.fuel_remaining,
                    required_condition = "remaining fuel at or above zero",
                ),
            ],
        ),
    )

def check_trajectory(
    source: DeductionInput[types.AcceptedPlan],
) -> types.LandingAssessment:
    hypothesis = source.context.value.value
    trajectory = simulate_trajectory(hypothesis)
    checks = check_constraints(trajectory, hypothesis.mission)
    return build_landing_assessment(
        source.context,
        trajectory,
        checks,
    )

def validate_safe_plan(
    source: DeductionInput[types.LandingAssessment],
) -> Result[
    Validated[
        value: Computed[types.PlanHypothesis],
        types.SafeUnderModel(value),
    ],
    types.LunarLandingError,
]:
    computed = source.context.plan.value
    return validate[
        types.SafeUnderModel(computed)
    ](
        computed,
        validator = "lunar-lander-simulator-v1",
        require = [source.context.accepted],
    )
```

</details>

The simulator introduces provenance at the exact computation boundaries.

```prism
return compute(trajectory, procedure = "lunar-trajectory-integrator-v1")
```

The constraint checker uses another named procedure. Neither `Computed`
value claims safety. The final function crosses the assurance boundary only
when every Boolean in the assessment is true.

```prism
return validate[
    SafeUnderModel(computed)
](
    computed,
    validator = "lunar-lander-simulator-v1",
    require = [source.context.accepted],
)
```

A failed requirement produces `ValidationError`. The application therefore
cannot return a safe plan after the loop exhausts its bound without reaching an
accepted assessment.

## Keep numerical search deterministic

Create `optimization.prism`. It scores constraint violations, constructs
nearby candidates, and selects the lowest score. Model generation has no
authority over numeric burn controls.

<details>
<summary>Show the complete optimizer</summary>

```prism title="optimization.prism"
from examples.language.refinement_loop.simulation import simulate_trajectory
from examples.language.refinement_loop.types import Burn, PlanHypothesis

def positive(value: Float) -> Float:
    return value if value > 0.0 else 0.0

def magnitude(value: Float) -> Float:
    return value if value >= 0.0 else -value

def clamp(value: Float, lower: Float, upper: Float) -> Float:
    below_upper = value if value < upper else upper
    return below_upper if below_upper > lower else lower

def revise_duration(burn: Burn, change: Float) -> Burn:
    return Burn(
        duration_seconds = clamp(burn.duration_seconds + change, 0.1, 60.0),
        throttle = burn.throttle,
        angle_degrees = 0.0,
    )

def revise_throttle(burn: Burn, change: Float) -> Burn:
    return Burn(
        duration_seconds = burn.duration_seconds,
        throttle = clamp(burn.throttle + change, 0.0, 1.0),
        angle_degrees = 0.0,
    )

def replace_burns(
    plan: PlanHypothesis,
    coast: Burn,
    braking: Burn,
    descent: Burn,
    terminal: Burn,
) -> PlanHypothesis:
    return PlanHypothesis(
        mission = plan.mission,
        strategy = plan.strategy,
        simulator_feedback = plan.simulator_feedback,
        prior_touchdown_x = plan.prior_touchdown_x,
        prior_touchdown_altitude = plan.prior_touchdown_altitude,
        prior_horizontal_speed = plan.prior_horizontal_speed,
        prior_vertical_speed = plan.prior_vertical_speed,
        prior_lander_angle = plan.prior_lander_angle,
        prior_fuel_remaining = plan.prior_fuel_remaining,
        coast = coast,
        braking = braking,
        descent = descent,
        terminal = terminal,
    )

def trajectory_violation_score(plan: PlanHypothesis) -> Float:
    mission = plan.mission
    bounds = simulate_trajectory(plan).value
    margin = 0.001
    return (
        positive(mission.landing_zone_min_x + margin - bounds.touchdown_x)
        + positive(bounds.touchdown_x - mission.landing_zone_max_x + margin)
        + 10.0 * positive(
            magnitude(bounds.touchdown_vx) - mission.max_horizontal_speed + margin
        )
        + 20.0 * positive(
            mission.min_vertical_speed + margin - bounds.touchdown_vy
        )
        + 20.0 * positive(bounds.touchdown_vy + margin)
        + 20.0 * positive(margin - bounds.touchdown_altitude)
        + 20.0 * positive(
            bounds.touchdown_altitude
            - mission.touchdown_altitude_tolerance
            + margin
        )
        + 10.0 * positive(
            bounds.touchdown_angle - mission.max_lander_angle + margin
        )
        + 20.0 * positive(mission.fuel_reserve + margin - bounds.fuel_remaining)
        + 20.0 * positive(
            margin - bounds.preterminal_clearance_lower_bound
        )
        + 40.0 * positive(bounds.terminal_entry_vy_upper_bound + margin)
        + 20.0 * positive(bounds.touchdown_vy + margin)
        + 20.0 * positive(margin - bounds.fuel_remaining)
    )

def best_candidate(
    candidates: List[PlanHypothesis],
    index: Int,
    best: PlanHypothesis,
    best_score: Float,
) -> PlanHypothesis:
    candidate = candidates[index]
    candidate_score = trajectory_violation_score(candidate)
    selected = (
        candidate
        if candidate_score < best_score
        else best
    )
    selected_score = candidate_score if candidate_score < best_score else best_score
    return (
        best_candidate(candidates, index + 1, selected, selected_score)
        if index + 1 < length(candidates)
        else selected
    )

def refine_plan(plan: PlanHypothesis) -> PlanHypothesis:
    coast = revise_duration(plan.coast, 0.0)
    braking = revise_duration(plan.braking, 0.0)
    descent = revise_duration(plan.descent, 0.0)
    terminal = revise_duration(plan.terminal, 0.0)
    normalized = replace_burns(plan, coast, braking, descent, terminal)
    bounds = simulate_trajectory(normalized).value
    duration_step = clamp(magnitude(bounds.touchdown_altitude) / 40.0, 0.1, 5.0)
    throttle_step = clamp(magnitude(bounds.touchdown_vy) / 20.0, 0.02, 0.25)
    candidates = [
        normalized,
        replace_burns(
            normalized,
            revise_duration(coast, -duration_step),
            braking,
            descent,
            terminal,
        ),
        replace_burns(
            normalized,
            revise_duration(coast, duration_step),
            braking,
            descent,
            terminal,
        ),
        replace_burns(
            normalized,
            revise_throttle(coast, -throttle_step),
            braking,
            descent,
            terminal,
        ),
        replace_burns(
            normalized,
            revise_throttle(coast, throttle_step),
            braking,
            descent,
            terminal,
        ),
        replace_burns(
            normalized,
            coast,
            revise_duration(braking, -duration_step),
            descent,
            terminal,
        ),
        replace_burns(
            normalized,
            coast,
            revise_duration(braking, duration_step),
            descent,
            terminal,
        ),
        replace_burns(
            normalized,
            coast,
            revise_throttle(braking, -throttle_step),
            descent,
            terminal,
        ),
        replace_burns(
            normalized,
            coast,
            revise_throttle(braking, throttle_step),
            descent,
            terminal,
        ),
        replace_burns(
            normalized,
            coast,
            braking,
            revise_duration(descent, -duration_step),
            terminal,
        ),
        replace_burns(
            normalized,
            coast,
            braking,
            revise_duration(descent, duration_step),
            terminal,
        ),
        replace_burns(
            normalized,
            coast,
            braking,
            revise_throttle(descent, -throttle_step),
            terminal,
        ),
        replace_burns(
            normalized,
            coast,
            braking,
            revise_throttle(descent, throttle_step),
            terminal,
        ),
        replace_burns(
            normalized,
            coast,
            braking,
            descent,
            revise_duration(terminal, -duration_step),
        ),
        replace_burns(
            normalized,
            coast,
            braking,
            descent,
            revise_duration(terminal, duration_step),
        ),
        replace_burns(
            normalized,
            coast,
            braking,
            descent,
            revise_throttle(terminal, -throttle_step),
        ),
        replace_burns(
            normalized,
            coast,
            braking,
            descent,
            revise_throttle(terminal, throttle_step),
        ),
    ]
    return best_candidate(
        candidates,
        0,
        normalized,
        trajectory_violation_score(normalized),
    )
```

</details>

The optimizer is ordinary pure Prism. It needs no reasoning declaration because
its job is numerical transformation. Its finite candidate list also keeps the
search reproducible and easy to trace.

This split applies a central Prism practice. Use deterministic computation for
work that has an exact implementation. Reserve generation for the portion that
needs linguistic judgment.

## Declare the reasoning topology

Create `reasoning.prism`. This file describes epistemic intent and data flow.
It contains no model, skill, policy, effect, failure, or provider choice.

```prism title="reasoning.prism"
from examples.language.refinement_loop.types import (
    AcceptedMission,
    AcceptedPlan,
    LandingAssessment,
    LunarSource,
    PlanHypothesis,
    PlausiblyExplainsFeedback,
    RefineTrajectory,
    SafeUnderModel,
    TrajectoryRefinementState,
)
from prism.reasoning.methods.abductive import Abductive
from prism.reasoning.methods.deductive import DeductionInput, Deductive

relation SupportTrajectoryHypothesis(
    source: LunarSource,
    target: AcceptedPlan,
) |~ PlausiblyExplainsFeedback(source.background.value, target.value, source.observation.value)

reasoning LunarLandingRefinement(
    source: LunarSource,
) -> Validated[
    value: Computed[PlanHypothesis],
    SafeUnderModel(value),
]:
    sequence:
        repeat refinement_policy(10, until = finding.accepted):
            [candidate: Abductive[
                AcceptedPlan,
                AcceptedMission,
                Evidence[PlanHypothesis],
            ](source)] by SupportTrajectoryHypothesis
            [finding: Deductive[
                LandingAssessment,
                AcceptedPlan,
            ](DeductionInput(context = candidate))]
            [source: RefineTrajectory(TrajectoryRefinementState(
                candidate = candidate,
                finding = finding,
                source = source,
            ))]
        [safe_plan: Deductive[
            Validated[
                value: Computed[PlanHypothesis],
                SafeUnderModel(value),
            ],
            LandingAssessment,
        ](DeductionInput(context = finding))]
    return safe_plan
```

The first occurrence is abductive because it proposes a plan that plausibly
explains and responds to the observations. The relation requires
`Supported[PlausiblyExplainsFeedback(...)]`, which records defeasible material
support.

The next occurrence is deductive because the simulator derives a concrete
assessment from an accepted candidate. `RefineTrajectory` is a structural
state transition, so an ordinary function type is appropriate.

The `repeat` block has a positive static bound and a pure exit condition.
Rebinding `source` carries the revised evidence into the next iteration.
After acceptance, `safe_plan` applies a final deductive assessment and returns
the contract established at the start.

The deductive reasoning type describes the epistemic operation.
`Validated` describes the resulting assurance. A deductive occurrence alone
does not create a kernel proof.

## Constrain the generated narrative with a skill

The generated portion has one narrow responsibility. It explains how proposed
burns respond to current feedback. Create the Open Agent Skill source.

```markdown title="skills/lunar-refinement-narrator/SKILL.md"
---
name: lunar-refinement-narrator
description: Explain a simulator-guided lunar landing refinement using only typed mission data, feedback, and proposed controls.
metadata:
  version: "1.0.0"
---

# Lunar refinement narrator

Produce the `PlanNarrative` for the supplied `ExplainRefinement` task.

- Inspect every feedback constraint whose `satisfied` field is false.
- Ground the strategy in the supplied observed values and required conditions.
- Explain how the proposed coast, braking, descent, and terminal burns address those failures.
- Mention a fuel, velocity, clearance, or attitude trade-off when it is relevant.
- Treat the proposed burn controls as immutable. Do not invent or modify numerical controls.
- Do not claim that the proposed plan is safe, accepted, or converged before simulator validation.
- If feedback is inactive, describe the proposed controls as an initial simulation candidate.
- Return only the requested structured `PlanNarrative`, with a concise `strategy`.
```

Build the skill against its exact task type.

```bash
uv run prism build skill \
  examples/language/refinement_loop/skills/lunar-refinement-narrator \
  --contract examples.language.refinement_loop.types.ExplainRefinement \
  --out examples/language/refinement_loop/lunar_refinement_skill
```

The build emits the typed artifact imported by the Prism program. The checked
example contains the following generated module.

<details>
<summary>Show the generated skill module</summary>

```prism title="lunar_refinement_skill.prism"
from examples.language.refinement_loop.types import ExplainRefinement

lunar_refinement_narrator_skill: Skill[ExplainRefinement] = skill_artifact[ExplainRefinement](
    "lunar-refinement-narrator",
    "1.0.0",
    "lunar-refinement-narrator",
    "Explain a simulator-guided lunar landing refinement using only typed mission data, feedback, and proposed controls.",
    "# Lunar refinement narrator\n\nProduce the `PlanNarrative` for the supplied `ExplainRefinement` task.\n\n- Inspect every feedback constraint whose `satisfied` field is false.\n- Ground the strategy in the supplied observed values and required conditions.\n- Explain how the proposed coast, braking, descent, and terminal burns address those failures.\n- Mention a fuel, velocity, clearance, or attitude trade-off when it is relevant.\n- Treat the proposed burn controls as immutable. Do not invent or modify numerical controls.\n- Do not claim that the proposed plan is safe, accepted, or converged before simulator validation.\n- If feedback is inactive, describe the proposed controls as an initial simulation candidate.\n- Return only the requested structured `PlanNarrative`, with a concise `strategy`.",
    "{}",
)
```

</details>

The skill constrains generation and supplies instructions. The agent still
declares `AI.Generate` and `Context.Disclose`, and the application still
receives authority for those effects explicitly.

## Materialize candidate generation and feedback

Create `refinement.prism`. This module supplies executable callables for the
abductive candidate, its relation, and the state transition.

<details>
<summary>Show the complete refinement module</summary>

```prism title="refinement.prism"
from examples.language.refinement_loop.lunar_refinement_skill import lunar_refinement_narrator_skill
from examples.language.refinement_loop.types import (
    AcceptedPlan,
    ExplainRefinement,
    LunarSource,
    LunarLandingError,
    PlanHypothesis,
    PlanNarrative,
    PlanWellFormed,
    PlausiblyExplainsFeedback,
    TrajectoryRefinementState,
)
from examples.language.refinement_loop.optimization import refine_plan
from prism.reasoning.methods.abductive import AbductionInput

def prepare_plan_request(
    source: LunarSource,
) -> ExplainRefinement:
    proposed = source.observation.value
    return ExplainRefinement(
        mission = source.background.value,
        feedback = proposed.simulator_feedback,
        proposed_plan = proposed,
    )

agent refinement_narrator(
    task: ExplainRefinement,
) -> Result[Generated[PlanNarrative], ModelFailure]
    ! {AI.Generate, Context.Disclose}:
    skills: Skills[ExplainRefinement] = [lunar_refinement_narrator_skill]

def assemble_plan_hypothesis(
    generated: Generated[PlanNarrative],
    source: LunarSource,
) -> Computed[PlanHypothesis]:
    requested = source.observation.value
    plan = PlanHypothesis(
        mission = source.background.value,
        strategy = generated.value.strategy,
        simulator_feedback = requested.simulator_feedback,
        prior_touchdown_x = requested.prior_touchdown_x,
        prior_touchdown_altitude = requested.prior_touchdown_altitude,
        prior_horizontal_speed = requested.prior_horizontal_speed,
        prior_vertical_speed = requested.prior_vertical_speed,
        prior_lander_angle = requested.prior_lander_angle,
        prior_fuel_remaining = requested.prior_fuel_remaining,
        coast = requested.coast,
        braking = requested.braking,
        descent = requested.descent,
        terminal = requested.terminal,
    )
    return compute(plan, procedure = "lunar-plan-control-assembly-v1")

def validate_plan_hypothesis(
    computed: Computed[PlanHypothesis],
    source: LunarSource,
) -> Result[AcceptedPlan, ValidationError]:
    plan = computed.value
    return validate[PlanWellFormed(computed)](
        computed,
        validator = "lunar-plan-v1",
        require = [
            plan.mission == source.background.value,
            plan.strategy != "",
            plan.coast.duration_seconds > 0.0,
            plan.coast.throttle >= 0.0,
            plan.coast.throttle <= 1.0,
            plan.braking.duration_seconds > 0.0,
            plan.braking.throttle >= 0.0,
            plan.braking.throttle <= 1.0,
            plan.descent.duration_seconds > 0.0,
            plan.descent.throttle >= 0.0,
            plan.descent.throttle <= 1.0,
            plan.terminal.duration_seconds > 0.0,
            plan.terminal.throttle >= 0.0,
            plan.terminal.throttle <= 1.0,
        ],
    )

def prepare_refinement(
    state: TrajectoryRefinementState,
) -> LunarSource:
    prior_candidate = state.candidate.value.value
    optimized = refine_plan(prior_candidate)
    revised = PlanHypothesis(
        mission = state.source.background.value,
        strategy = prior_candidate.strategy,
        simulator_feedback = state.finding.counterexample,
        prior_touchdown_x = state.finding.trajectory.value.touchdown_x,
        prior_touchdown_altitude = state.finding.trajectory.value.touchdown_altitude,
        prior_horizontal_speed = state.finding.trajectory.value.touchdown_vx,
        prior_vertical_speed = state.finding.trajectory.value.touchdown_vy,
        prior_lander_angle = state.finding.trajectory.value.touchdown_angle,
        prior_fuel_remaining = state.finding.trajectory.value.fuel_remaining,
        coast = optimized.coast,
        braking = optimized.braking,
        descent = optimized.descent,
        terminal = optimized.terminal,
    )
    observation = map_evidence(
        state.source.observation,
        value = revised,
        transformation = (
            "deterministic simulator counterexample attached to next abductive request"
        ),
    )
    return AbductionInput(
        background = state.source.background,
        observation = observation,
    )

def support_trajectory_hypothesis(
    source: LunarSource,
    target: AcceptedPlan,
) -> Result[
    Supported[PlausiblyExplainsFeedback(source.background.value, target.value, source.observation.value)],
    Never,
]:
    hypothesis = target.value.value
    feedback = source.observation.value
    policy: MaterialPolicy[
        PlanHypothesis,
        PlausiblyExplainsFeedback(source.background.value, target.value, source.observation.value),
        Never,
    ] = material_policy(
        "lunar-trajectory-abduction-v1",
        require = [
            hypothesis.mission == source.background.value,
            feedback.mission == source.background.value,
            hypothesis.simulator_feedback.active == feedback.simulator_feedback.active,
            hypothesis.simulator_feedback.assessment_time == feedback.simulator_feedback.assessment_time,
            hypothesis.simulator_feedback.constraints == feedback.simulator_feedback.constraints,
            hypothesis.prior_touchdown_x == feedback.prior_touchdown_x,
            hypothesis.prior_touchdown_altitude == feedback.prior_touchdown_altitude,
            hypothesis.prior_horizontal_speed == feedback.prior_horizontal_speed,
            hypothesis.prior_vertical_speed == feedback.prior_vertical_speed,
            hypothesis.prior_lander_angle == feedback.prior_lander_angle,
            hypothesis.prior_fuel_remaining == feedback.prior_fuel_remaining,
        ],
    )
    return source.observation |~[policy] PlausiblyExplainsFeedback(
        source.background.value,
        target.value,
        source.observation.value,
    )

workflow materialize_abductive_plan(
    source: LunarSource,
) -> AcceptedPlan
    fails LunarLandingError
    ! {AI.Generate, Context.Disclose}:
    sequence:
        [request: prepare_plan_request(source)]
        [generated: refinement_narrator(request)]
        [computed: assemble_plan_hypothesis(generated, source)]
        [validated: validate_plan_hypothesis(computed, source)]
    return validated
```

</details>

Four boundaries deserve close attention.

### Limit the agent task

`prepare_plan_request` gives the agent the mission, simulator feedback, and
already selected numeric controls. The `refinement_narrator` agent returns
only `Generated[PlanNarrative]`.

### Validate generated content before stronger use

`assemble_plan_hypothesis` copies the numeric controls from the deterministic
request and adds the generated strategy. It wraps the assembled result in
`Computed[PlanHypothesis]`. `validate_plan_hypothesis` then checks the
mission identity, nonempty strategy, positive durations, and throttle ranges.

The generated text retains its trace through the computed assembly. Validation
adds assurance about the exact assembled plan.

### Preserve evidence through refinement

`prepare_refinement` attaches the simulator counterexample and revised
controls with `map_evidence`. Upstream provenance remains available, and the
named transformation records how the next observation was formed.

### Materialize support with a named policy

The abstract `SupportTrajectoryHypothesis` relation requires material support.
Its implementation creates a `MaterialPolicy` and checks that the candidate
preserves the mission, counterexample, and prior trajectory values.

```prism
return source.observation |~[policy] PlausiblyExplainsFeedback(
    source.background.value,
    target.value,
    source.observation.value,
)
```

This certificate is `Supported[P]`. Safety receives a separate deterministic
validation after simulation.

## Bind every abstract occurrence

Create `materialization.prism`. A direct named call binds each occurrence and
the attached relation exactly once.

```prism title="materialization.prism"
from examples.language.refinement_loop.simulation import (
    check_trajectory,
    validate_safe_plan,
)
from examples.language.refinement_loop.reasoning import LunarLandingRefinement
from examples.language.refinement_loop.refinement import (
    materialize_abductive_plan,
    prepare_refinement,
    support_trajectory_hypothesis,
)

lunar_landing_refinement = LunarLandingRefinement(
    candidate = materialize_abductive_plan,
    candidate_by = support_trajectory_hypothesis,
    finding = check_trajectory,
    safe_plan = validate_safe_plan,
    source = prepare_refinement,
)
```

The names mirror `reasoning.prism`.

| Abstract occurrence | Executable binding |
| --- | --- |
| `candidate` | `materialize_abductive_plan` |
| `candidate_by` | `support_trajectory_hypothesis` |
| `finding` | `check_trajectory` |
| `source` | `prepare_refinement` |
| `safe_plan` | `validate_safe_plan` |

Prism infers the materialized workflow result, failures, and effects from these
callables. Missing, extra, or incompatible bindings fail static checking.

## Wire the application entry

Create `main.prism`. The entry point supplies concrete mission data, validates
the mission, records the initial plan as evidence, and executes the declared
reasoning through its materialization.

```prism title="main.prism"
from examples.language.refinement_loop.materialization import lunar_landing_refinement
from examples.language.refinement_loop.reasoning import LunarLandingRefinement
from examples.language.refinement_loop.types import (
    Burn,
    Counterexample,
    LunarSource,
    LunarLandingError,
    MissionConstraints,
    MissionAccepted,
    PlanHypothesis,
    SafeUnderModel,
)
from prism.reasoning.methods.abductive import AbductionInput

def main(
    model_access: ModelGenerate,
    disclosure: ContextDisclose,
) -> Result[
    Validated[value: Computed[PlanHypothesis], SafeUnderModel(value)],
    LunarLandingError,
] ! {AI.Generate, Context.Disclose}:
    mission_specification = MissionConstraints(
        description = "Land a throttleable 2D lunar lander safely inside the target zone.",
        initial_x = 16.5,
        initial_altitude = 250.111,
        initial_vx = 0.0,
        initial_vy = -5.0,
        dry_mass = 100.0,
        initial_fuel = 20.0,
        lunar_gravity = 1.62,
        fuel_burn_rate = 0.8,
        fuel_reserve = 8.0,
        max_thrust = 450.0,
        landing_zone_min_x = 0.0,
        landing_zone_max_x = 25.0,
        max_horizontal_speed = 0.5,
        min_vertical_speed = -1.5,
        max_lander_angle = 5.0,
        touchdown_altitude_tolerance = 0.5,
    )
    mission = try validate[MissionAccepted(mission_specification)](
        mission_specification,
        validator = "lunar-mission-v1",
        require = [mission_specification.description != ""],
    )
    initial_hypothesis = PlanHypothesis(
        mission = mission.value,
        strategy = "Coast, then brake and arrest vertical speed near touchdown.",
        simulator_feedback = Counterexample(
            active = False,
            assessment_time = 0.0,
            constraints = [],
        ),
        prior_touchdown_x = 0.0,
        prior_touchdown_altitude = mission.value.initial_altitude,
        prior_horizontal_speed = mission.value.initial_vx,
        prior_vertical_speed = 0.0,
        prior_lander_angle = 0.0,
        prior_fuel_remaining = mission.value.initial_fuel,
        coast = Burn(duration_seconds = 8.0, throttle = 0.0, angle_degrees = 0.0),
        braking = Burn(duration_seconds = 7.0, throttle = 0.7, angle_degrees = 8.0),
        descent = Burn(duration_seconds = 6.0, throttle = 0.95, angle_degrees = 0.0),
        terminal = Burn(duration_seconds = 3.0, throttle = 0.4, angle_degrees = 0.0),
    )
    source: LunarSource = AbductionInput(
        background = mission,
        observation = observe(
            initial_hypothesis,
            source = "lunar landing mission and simulator feedback",
            method = "mission specification with refinement trace",
        ),
    )
    return solve LunarLandingRefinement(source) using lunar_landing_refinement(source)
```

The mission values are application inputs for this example. Provider names,
credentials, endpoints, and model settings remain outside reusable Prism
source.

The `main` signature exposes both runtime permissions and the complete effect
row. Its last line invokes the reasoning and executable workflow together.

```prism
return solve LunarLandingRefinement(source) using lunar_landing_refinement(source)
```

This form asks the runtime to verify that the workflow materializes the stated
reasoning and returns its exact result type.

## Check, compile, and run

Check the real entry point. Module checking follows every import.

```bash
uv run prism check examples/language/refinement_loop/main.prism
```

A successful check reports `"status": "ok"`.

Compile the program and inspect the inferred entry contract.

```bash
uv run prism compile examples/language/refinement_loop/main.prism
```

The compiled `main` returns
`Result[Validated[value: Computed[PlanHypothesis], SafeUnderModel(value)], LunarLandingError]`
and declares `AI.Generate` plus `Context.Disclose`.

Run the complete loop with deterministic synthetic generation.

```bash
uv run prism run examples/language/refinement_loop/main.prism --handler fake
```

The run finishes with `"status": "accepted"`. Its trace records the two
permissions, mission validation, observed evidence, materialized reasoning,
each repeated occurrence, material support, deterministic computations, and
final validation.

A live model can replace the fake handler without changing the program's types
or assurance boundaries. Runtime configuration supplies provider and model
selection.

## Review the design

The finished program applies these Prism practices.

- The useful domain result was chosen before orchestration.
- Pure domain computation remains in small typed functions.
- The reusable reasoning declaration contains only epistemic topology.
- Abduction proposes candidates and deduction evaluates explicit premises.
- Numerical revision remains deterministic.
- Generated, observed, computed, supported, and validated values keep distinct
  types.
- The repeat has a static bound, a checked exit condition, and explicit state.
- Every abstract occurrence and relation has one concrete binding.
- Effects and permissions appear at the callables that need them.
- The entry point executes the reasoning with `solve ... using ...`.

Continue with [reasoning types](../concepts/reasoning-types.md),
[relations and materialization](../concepts/relations-materialization.md), and
[execution and tracing](../concepts/execution-tracing.md) for focused accounts
of the contracts used here.
