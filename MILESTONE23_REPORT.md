# Milestone 23 — Objective-Driven Simulation Optimization

## Delivered

M23 adds a reproducible, bounded, single-objective optimization capability
that executes candidate parameter vectors through the common M9 runner.
Users specify numeric search bounds for exact M8 `user_parameter` paths, an
output metric to minimize/maximize, an optional compiled baseline, replications
and optional metric constraints. The seeded uniform random search generates
unique candidates within a fixed 100-M9-execution budget.

The optimizer summarizes candidate objective means and population standard
deviations, evaluates constraints on candidate-level means, retains failed and
incomplete candidates as ineligible records, and identifies the best feasible
candidate. A baseline improvement is reported only when the baseline is also
feasible. M9 results are integrity-checked; M23 reports are fingerprinted and
exportable to CSV.

## Integration

- M9 is the shared execution path; optimization does not implement duplicate
  backend execution logic.
- Candidate parameter values can modify only approved numeric M8
  `user_parameter` fields; conceptual bindings remain immutable.
- M10 remains the grid/comparison workflow, and M11 remains uncertainty,
  sensitivity and robustness analysis.
- The main CLI adds option 18 to run optimization and option 19 to inspect an
  integrity-verified M23 report. A standalone `optimization.cli` is also
  provided.
- The M23 execution integration tests cover ABM, mathematical, data-driven
  and system dynamics. The orchestration also uses the shared DES M9 backend;
  full DES runtime verification requires `simpy`.

## Verification

Packaging-environment verification: 13 M23 tests passed; 542 tests passed
with the DES test directory excluded; 20 DES replay regression tests passed;
Python compilation and standalone CLI help passed. The full suite could not be
collected in this environment because `simpy` and `groq` were unavailable.
The user's Windows full-suite verification remains required.

## V1 limitations

M23 uses uniform random search rather than an adaptive or guaranteed global
optimizer. It supports one objective and optional metric constraints. It does
not include multi-objective Pareto optimization, Bayesian or evolutionary
search, gradient-based methods, automatic bounds/objective inference, or
distributed execution. ABM comparisons use M9's sequential seeds rather than
paired common-random-number streams. Extra replications for deterministic
backends generally repeat the same output. Optimization results are
conditional on the selected model and plan and do not prove real-world
optimality, causal validity or scientific truth.
