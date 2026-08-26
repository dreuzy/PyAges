# Scientific documentation audit for GMD readiness

**Audit date:** 26 August 2026
**Scope:** public Python definitions and the scientific paths for convolution,
inverse-Gaussian LPMs, objectives, priors/proposals, and Metropolis-Hastings.

## Finding

The initial inventory reported 489 documented public definitions out of 501,
with 203 docstrings shorter than eight words. Before the targeted edits, a
repeat AST inventory on the refactored tree found 466 documented definitions
out of 478 and 184 shorter than eight words. After this pass, the same heuristic
finds 463 out of 474 documented and 177 shorter than eight words. The changing
denominator reflects concurrent removal or renaming of definitions, not a loss
of documentation.

The 11 remaining apparent omissions are simple forwarding properties, nested
serialization/registration callbacks, and plotting/timing helpers. None
defines a scientific equation, unit, boundary, tolerance, prior, likelihood,
or sampling convention, so this pass deliberately did not add filler solely
to make the count reach 100%.

Neither count is a scientific-quality metric. Many short accessors are
adequately self-describing, while several long docstrings previously omitted a
decisive equation or convention. The GMD-relevant risk was concentrated in the
following paths.

| Priority | Previous ambiguity | Reproducibility risk | Applied documentation |
| --- | --- | --- | --- |
| critical | finite convolution window and tail handling | independent implementation could renormalize omitted old mass | equation, closed endpoints, units, and non-renormalization in code and {doc}`../scientific-methods` |
| critical | adaptive-grid tolerance fields | defaults could be mistaken for error bounds or physical parameters | exact acceptance criterion, units, failure behavior, and sensitivity requirement |
| critical | inverse-Gaussian ``mu`` | SciPy shape could be substituted for physical mean age | PDF, physical-to-SciPy map, support, shift, and stable CDF convention |
| critical | objective labels | $\chi^2$, $\sqrt{\chi^2/n}$, and $\tfrac12\log\chi^2$ could be compared as one quantity | explicit table of code and output conventions |
| critical | MH acceptance and transformed proposals | Jacobian or rejection repeats could be omitted | target, Hastings ratio, retention rule, seed, units, and diagnostics caveat |
| high | version and citation identity | beta artifact could be cited as released ``v1.0`` or assigned a placeholder DOI | explicit manuscript-target versus software-release policy in {doc}`../dev/versioning-citation` |

## Documentation policy applied

Documentation was expanded where it explains **why** a numerical branch
exists, defines a scientific quantity, or constrains an independent
implementation. Obvious property forwarding and plotting mechanics were not
expanded merely to increase word counts. The resulting hierarchy is:

1. code docstrings state the local contract, equation, units, boundary, and
   failure behavior needed while reading the implementation;
2. {doc}`../scientific-methods` is the concise methods reference linking code,
   user configuration, tests, and reports;
3. thematic pages under `science/` explain interpretation and study scope
   without redefining normative equations or numerical defaults;
4. change and qualification reports retain derivations, benchmarks, migration
   history, and limitations;
5. article manifests link each reported calculation to commits, inputs,
   scripts, environments, seeds, and outputs.

This structure supports scientifically equivalent reproduction without
turning source files into a duplicate manuscript.

## Verification completed on 26 August 2026

- The manuscript numbering is aligned to revision v14: Table 3 is the
  PyAge--TracerLPM comparison and Table 4 is the shifted-exponential benchmark.
  Historical filenames such as `table3_final.*` are retained but labeled.
- The normative/thematic split was reviewed so equations, adaptive settings,
  objective transformations, and MH retention rules have one normative source.
- `pyage check`, `pyage list lpms`, and `pyage list tracers` pass and report 12
  registered LPMs and 13 distributed tracers.
- The targeted robustness/reproducibility tests pass (`9 passed`).
- A clean Sphinx HTML build with `-E -a -W --keep-going` succeeds for all
  sources, and the external-link build succeeds. One valid AGU DOI that returns
  HTTP 403 to automated clients is excluded by an exact URL rule; no DOI class
  or domain-wide exclusion is used.
- The Holten Dirichlet sensitivity cannot be independently checked from this
  checkout: its chains, pilots, historical manifest, and canonical Holten
  outputs are absent, and the recorded runner checksum differs from the current
  script. The maintainer reports that the work was completed separately; it
  remains locally `unvalidated` until that evidence is imported and reviewed.

## Remaining editorial actions before submission

- Import and independently review the completed external Holten Dirichlet
  sensitivity package, including chains, diagnostics, residual comparisons,
  environment, seeds, and checksums. Do not rerun it merely because the current
  checkout lacks the external evidence.
- Freeze the exact reviewed commit and dependency environment used for every
  final figure and table.
- Run and archive a tolerance-sensitivity result for any non-default
  ``TracerGridSettings`` used by the article.
- Report chain count, retained draws, $\hat R$, effective sample size, Monte
  Carlo uncertainty, and the actual proposal configuration for each Bayesian
  result; burn-in and thinning alone are insufficient.
- Replace manuscript wording that says only “objective” with the exact symbol
  and transformation used.
- Mint the DOI only from the immutable public release/archive; then update
  ``CITATION.cff`` and the article citation together and verify the archived
  metadata before submission.

These are release/submission gates rather than reasons to add mechanical
comments to the remaining short accessors.
