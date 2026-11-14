# M23 Objective-Driven Simulation Optimization

M23 adds a bounded optimization loop on top of the existing M8/M9 execution
contracts. It is deliberately separate from M10 and M11:

- M10 evaluates user-specified Cartesian grids and summarizes differences.
- M11 propagates specified input uncertainty and screens sensitivity/robustness.
- M23 searches within explicit numeric parameter bounds to find candidates
  that optimize one selected output metric while satisfying optional output
  constraints.

## Python API

```python
from compilation import load_artifact
from execution import save_result
from optimization import (
    MetricConstraint, OptimizationObjective, OptimizationPlan,
    SearchParameter, export_summary_csv, optimize_parameters, save_report,
)

artifact = load_artifact("outputs/model_m8_agent_based_specification.json")
plan = OptimizationPlan(
    search_parameters=(
        SearchParameter("agents[0].attributes.trust", 0.0, 1.0),
        SearchParameter("termination.value", 1, 20),
    ),
    objective=OptimizationObjective(
        "derived:abm:Person:contributions:sum", "maximize"
    ),
    candidate_count=12,
    replications=2,
    search_seed=20261115,
    include_baseline=True,
    constraints=(
        MetricConstraint("steps_completed", "<=", 20.0),
    ),
)

m9_result, m23_report = optimize_parameters(
    artifact, plan, execution_base_seed=700
)
save_result(m9_result, "outputs/m23_m9_execution.json")
save_report(m23_report, "outputs/m23_optimization_report.json")
export_summary_csv(m23_report, "outputs/m23_candidates.csv")
```

Every search parameter must resolve to an exact scalar numeric M8
`user_parameter` binding. Bounds must preserve the field's numeric type. The
optimizer does not change conceptual-element bindings, infer parameter
semantics, or invent equations. The optional baseline is the compiled M8
value for every selected path and must lie within the supplied search bounds.

The M9 execution budget is capped at 100 total runs, including replications
and the baseline. The default algorithm is seeded uniform random search. Each
integer parameter is sampled uniformly from its inclusive integer bounds;
each float parameter is sampled uniformly from its inclusive real interval.
Duplicate candidates are discarded. Candidate generation is reproducible for
a fixed plan/search seed.

The objective and each constraint are evaluated using the mean metric over all
requested replications for a candidate. A candidate is eligible for selection
only if every requested replication completed and every objective/constraint
metric was available in every successful run. Failed or incomplete candidates
remain in the report but cannot be selected. If no feasible candidate exists,
`best_parameter_set` is `None`.

## CLI

The main application menu exposes M23 as option 18 and report inspection as
option 19. A non-interactive command is also available:

```powershell
python -m optimization.cli --artifact outputs/model_m8_agent_based_specification.json --plan scenarios/optimization/abm_random_search_plan.json --output-dir outputs --execution-base-seed 700
```

The sample plan is illustrative for ABM artifacts with the exact named M8
parameter bindings. Adjust its paths to the selected artifact. The CLI writes
a normal M9 execution result, a fingerprinted M23 report and a candidate CSV.

## Interpretation and V1 limits

M23 implements single-objective optimization with optional metric constraints.
It does not guarantee a global optimum; random search can miss narrow or
interacting optima. Search bounds, objective choice, constraints, solver,
replications and model structure all affect the result. Optimization is
conditional on the selected M8 model and does not prove empirical validity or
causation.

ABM uses M9's sequential random seeds across candidates, not paired common
random-number streams; comparisons can therefore reflect both parameter and
stochastic variation. The current DES, mathematical, data-driven and system
dynamics backends are deterministic, so extra replications repeat the same
model execution and are generally unnecessary. M23 V1 does not implement
multi-objective Pareto search, gradient-based optimization, Bayesian
optimization, evolutionary algorithms, automatic bound inference, surrogate
models, distributed execution or adaptive search budgets.
