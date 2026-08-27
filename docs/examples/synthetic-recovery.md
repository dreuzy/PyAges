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

From a source checkout with PyAge installed:

```bash
python -m examples.synthetic.lpm_recovery_single_date.run_lpm_recovery_single_date
```

The default runner reuses the reviewed, versioned synthetic observations, runs
the single-date Metropolis-Hastings workflow, and writes truth-aware summaries.
Its 5,000-step single chain is pedagogical; it is not a publication convergence
protocol.

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
