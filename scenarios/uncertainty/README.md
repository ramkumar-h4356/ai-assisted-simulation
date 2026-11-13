# M11 uncertainty-plan examples

`plan_example.json` demonstrates the M11 JSON contract for an ABM artifact
that explicitly declares both initial trust fields as M8 `user_parameter`
bindings. The target paths are examples: inspect the bindings and native model
values in your selected M8 artifact before using or editing the plan.

Supported distributions:

- `uniform`: requires finite `lower` and `upper` values. Integer model fields
  use inclusive integer sampling; floating-point fields use uniform real
  sampling.
- `triangular`: requires finite `lower`, `upper` and `mode` values. The mode
  is the most likely input value. Integer model fields are rounded to integers
  and clipped to the declared bounds.

M11 V1 allows 3–100 samples and accepts numeric model parameters only. All
sampled paths must be exact M8 `user_parameter` bindings and their bounds must
match the target's numeric type. Sampling uses `sampling_seed` for repeatable
input vectors. ABM execution may additionally ask for an execution base seed;
M9 records the actual seed for each run.

Robustness criteria are optional. Operators are `<=`, `>=` and `between`.
A criterion is evaluated against a numeric metric name available in the M9
result or derived from its retained trace. Multiple criteria are also evaluated
jointly on runs where every criterion metric is available.

The reported robustness fraction is an observed proportion in this finite
experiment, not a calibrated real-world probability. The ABM output spread
includes stochastic execution variation in addition to input variation.
