# Ploemeur F09 golden qualification — 2026-08-29

## Scope and decision

This review resolves the qualification question attached to the short, seeded
Ploemeur F09 extensive-test fixture. The fixture is approved as a deterministic
software-regression baseline. It is explicitly **not** approved as a converged
posterior estimate or as independent scientific evidence for the Ploemeur
hydrogeological interpretation.

That distinction is intentional. A 200-transition chain with 15 retained rows
is useful for detecting software drift, but it is too short for split-Rhat,
effective-sample-size, Monte Carlo standard-error, or stable posterior-shape
claims. Publication inference must continue to use the separately qualified
long-chain campaigns and their diagnostics.

## Reproduction evidence

The current fixture contains 62 records. The August 2026 refresh changed 312
numeric fields in 60 records while preserving the schema. The changes affect
objective means and standard deviations for all 60 changed records, native
parameter means and standard deviations for 38 records, and inverse-Gaussian
shape summaries for 20 records. They span `successive`,
`successive_with_prior`, `span_with_prior`, and `span_full` modes.

The changed seeded sequence follows the calibration hardening carried out in
August 2026: explicit `CalibrationProblem` composition, validated proposal
configuration, deterministic initial-state precedence, exact prior support in
log space, and retention of the current joint state after rejection. The
later 1.0 stabilization repeated the golden update after the final sampler and
prior organization. These are algorithm/protocol changes, not formatting-only
changes, so retaining the older numbers would have been misleading.

Evidence for the current tree:

- two independent Ubuntu 24.04/Python 3.12 generations previously produced
  the same candidate baseline;
- the qualified Windows/Python 3.12 environment ran the complete extensive
  suite on 2026-08-29: 1,096 tests passed in 1,163.79 seconds;
- a separately retained Windows `double_prior` execution reproduced all 36
  applicable golden records exactly (maximum observed relative difference
  `0.0`);
- every retained table contained 15 rows, every `param_in_bounds` flag was
  true, and every objective value was finite and non-negative.

The Windows execution used Python 3.12, the direct versions constrained by
`install/constraints.txt`, seed 12345, 200 transitions, and the repository's
canonical `sites/ploemeur/params/ploemeur_F09.yaml` configuration. Its source
tree was byte-equivalent to merged commit
`d9e1a69922f5dd2096e9fa4003ce7715dbf7bc33`.

## Acceptance and trajectory inspection

Across the 36 `double_prior` Metropolis-Hastings runs, transition acceptance
ranged from `0.01` to `0.85`, with median `0.065` and mean `0.1483`. Thirty
runs were below `0.15`, and 15 were below `0.05`. Retained parameter tables had
between 2 and 15 unique joint states, with median 9.

For the requested `F09_2019_2020` representative window:

- `exp_shifted`: acceptance `0.01`, 2 unique retained states, objective range
  `0.425295`–`0.426881`;
- `ig_shifted`: acceptance `0.055`, 9 unique retained states, objective range
  `0.391313`–`0.422579`.

The inspected `exp_shifted` acceptance trajectory contains one accepted
retained transition and long repeated-state plateaus. This is correct Markov
chain retention behavior and a useful regression signature, but it is direct
evidence against interpreting the 15-row summary as a converged posterior.

## Independent invariants and maintenance policy

The fixture's independent contract is limited to the following invariants:

1. every configured mode, well/date window, and LPM produces the expected
   record structure;
2. retained native parameters remain within declared LPM bounds;
3. objectives and parameter summaries remain finite, with non-negative
   objective values and standard deviations;
4. rejected proposals retain the current joint parameter state rather than
   constructing unpaired marginal samples;
5. identical seed, configuration, dependency baseline, and source tree produce
   the committed regression values on both Linux and Windows.

The golden may be updated only after an intentional algorithm or protocol
change is explained and reproduced independently. It must not be cited as
evidence of convergence. Because continuous daily replay no longer adds useful
qualification evidence, the extensive CI sentinel is reduced to weekly while
remaining available for manual dispatch before releases.
