# Experiment-grid examples

M10 grid-factor inputs are JSON arrays of objects with `target_path` and
`levels` fields. See `M10_ARCHITECTURE.md` for a complete example.

A factor path is valid only when the selected M8 compilation artifact contains
that exact field and marks it with a `user_parameter` provenance binding. The
same JSON grid is not guaranteed to apply to a different M8 artifact.
