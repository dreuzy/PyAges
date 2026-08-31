# Synthetic parameter-recovery example

The synthetic single-date example is the recommended first calibration case.
It generates observations from a known shifted-exponential LPM, adds controlled
noise, estimates the same LPM family, and compares the posterior with the known
truth.

The generation settings define:

| Setting | Value |
| --- | --- |
| LPM | `exp_shifted` |
| True `mu` | 28 years |
| True `shift` | 4 years |
| Tracers | CFC-11, CFC-12, CFC-113, SF6 |
| Relative observation error | 4% |
| Random seed | 12345 |

## Run

From a source checkout with PyAges installed:

```bash
python -m examples.synthetic.lpm_recovery_single_date.run_lpm_recovery_single_date
```

The default runner reuses the reviewed, versioned synthetic observations, runs
the single-date Metropolis-Hastings workflow, and writes truth-aware summaries.
Its 5,000-step single chain is pedagogical; it is not a publication convergence
protocol.

## Run the multi-chain qualification

The source checkout includes a second, **Unreleased** configuration. It is not
available in the `pyages==1.0.1` package from PyPI:

```bash
pyages run examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date_multichain.yaml
```

This profile uses four `bounds_stratified` starts, 1,500 pilot transitions and
4,000 production transitions per chain, `nskip: 1`, master seed `20260831`, and
required R-hat `< 1.01` plus bulk/tail ESS `>= 300`. It retains 2,999 rows per
chain, or 11,996 rows after qualification and pooling. The current sequential
runner performs 22,000 MH transitions.

The corresponding extensive test is:

```bash
python -m pytest -q --run-extensive tests/examples/test_synthetic_recovery_multichain_scientific.py
```

It verifies marginal recovery of `mu=28` and `shift=4`, their two-dimensional
joint ellipse, recovery of `mu+shift=32`, and all four fitted latent tracer
responses. The fixed-seed run has maximum R-hat `1.003066`, minimum bulk ESS
`1540.59`, and minimum tail ESS `1647.96`.

The fitted response distribution is not posterior predictive: it varies the
retained LPM parameters but does not draw new observation noise. The result
qualifies this one versioned noisy realization, not repeated-noise coverage.
Operational details and trace inspection are in
{doc}`../user-guide/multichain-mh`.

Regeneration is deliberately explicit because a numerical-method change can
alter the versioned reference data:

```bash
python -m examples.synthetic.lpm_recovery_single_date.run_lpm_recovery_single_date --regenerate
```

Review the resulting Git diff and the relevant scientific invariants before
accepting regenerated values.

## Interpret

Start with `parameter_recovery_summary.txt`. It records each true parameter,
posterior mean and standard deviation, and the mean-minus-truth difference.
Then compare:

- `01_data_model_space.png`: noisy observations, reachable models, posterior
  samples, and the noise-free true model;
- `02_parameter_summary.png`: marginal posterior distributions and true
  parameter values;
- `03_objective_summary.png`: sampled objective landscape, posterior samples,
  and truth.

The known truth makes parameter recovery visible, but it does not eliminate
finite-chain Monte Carlo error or structural non-identifiability. Continue
with {doc}`../science/inference` before interpreting field results.

The source files and notebook remain in
`examples/synthetic/lpm_recovery_single_date/` on GitHub.
