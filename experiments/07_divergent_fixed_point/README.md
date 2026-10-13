# Solution exists but fixed-point iteration diverges

Case: `07_divergent_fixed_point`.

- `config.json`: parameters and connections used by the master.
- `experiment.json`: declared outcomes and comparison tolerances.
- `models/`: separate adder SLX models and the coupled Simulink reference.
- `fmus/`: generated FMUs, transferred as pipeline artifacts.
- `reference/`: raw MATLAB trace, comparison CSV and reference status.
- `diagram.png`: the tested FMU connection graph.
- `setup.m`: local MATLAB entry point for this case.

Master expectation: **nonconvergence**. MATLAB expectation: **success**.

MATLAB should calculate a = b = -1; the master's current fixed-point iteration from zero should report nonconvergence. This is an expected solver limitation.

See the [shared setup and pipeline instructions](../../README.md).
