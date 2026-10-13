# Inconsistent equations: no solution

Case: `06_unit_gain_inconsistent`.

- `config.json`: parameters and connections used by the master.
- `experiment.json`: declared outcomes and comparison tolerances.
- `models/`: separate adder SLX models and the coupled Simulink reference.
- `fmus/`: generated FMUs, transferred as pipeline artifacts.
- `reference/`: raw MATLAB trace, comparison CSV and reference status.
- `diagram.png`: the tested FMU connection graph.
- `setup.m`: local MATLAB entry point for this case.

Master expectation: **nonconvergence**. MATLAB expectation: **algebraic_failure**.

The equations have no solution. The expected solver error is recorded; no successful reference CSV is fabricated.

See the [shared setup and pipeline instructions](../../README.md).
