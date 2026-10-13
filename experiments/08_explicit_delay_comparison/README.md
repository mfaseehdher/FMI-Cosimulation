# Explicit previous-step delay

Case: `08_explicit_delay_comparison`.

- `config.json`: parameters and connections used by the master.
- `experiment.json`: declared outcomes and comparison tolerances.
- `models/`: separate adder SLX models and the coupled Simulink reference.
- `fmus/`: generated FMUs, transferred as pipeline artifacts.
- `reference/`: raw MATLAB trace, comparison CSV and reference status.
- `diagram.png`: the tested FMU connection graph.
- `setup.m`: local MATLAB entry point for this case.

Master expectation: **success**. MATLAB expectation: **success**.

See the [shared setup and pipeline instructions](../../README.md).
