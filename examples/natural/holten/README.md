# Holten benchmark example

This directory contains the reproducible, case-specific Holten benchmark based
on the April 2010 campaign described by Visser et al. (2013). It prepares local
tracer histories and well observations, runs the configured PyAges bootstrap
calibration, and produces the Holten-specific four-bin comparison.

Inputs are selected by `holten.yaml`. Source and prepared data remain local to
this directory; the generic PyAges package does not import the benchmark.

Run the complete workflow from the repository root:

```console
python examples/natural/holten/run_holten.py --mode full
```

Use `--mode prepare_only`, `calibration_only`, or `compare_only` for a partial
run, and `--wells <comma-separated-ids>` to restrict the wells.

Local products are written below `generated/benchmark/` in the `prepared`,
`pre_model`, `four_bin`, and `benchmark` subdirectories. Generic launcher
results use the configured PyAges result root and follow the standard workflow
output contract.

The full description of inputs, modes, outputs, scientific scope, optional
dependencies, and validation commands is in the
[online Holten documentation](../../../docs/examples/holten/README.md).

