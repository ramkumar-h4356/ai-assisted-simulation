# System Dynamics V1 (M22)

M22 adds deterministic stock-and-flow simulation. A model contains stocks (accumulated state), directed flows (rates moving quantity from a source stock to a target stock, or from/to the external environment), optional auxiliary equations, parameters, a finite time horizon and a fixed integration solver (`euler`, `heun`, `rk4`).

Expressions use the same restricted arithmetic/function allow-list as M20. Expressions are validated before execution and evaluated by a safe AST interpreter; Python code, attribute access, indexing, imports and arbitrary calls are rejected. Auxiliary equations are topologically ordered and circular dependencies are rejected. Flow rates must be finite and non-negative; direction is declared through source/target stocks. Optional stock `minimum` bounds are checked after each integration step.

V1 provides deterministic fixed-step integration, stock/auxiliary/flow snapshots, stock summaries, and trapezoidally integrated cumulative flow. It does not yet provide delay structures, table functions, stochastic flows, hybrid event coupling, automatic loop discovery, units algebra or adaptive/stiff solvers. A stock-flow diagram is not itself evidence that the model is empirically valid.

Run `python -m simulations.system_dynamics.demo` for an illustrative SIR stock-flow model. The example is explanatory and uses invented demonstration parameters.
