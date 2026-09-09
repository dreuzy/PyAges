# Maintainership and continuity

PyAges currently has one maintainer. The release process must therefore be
usable and auditable without pretending that a second developer is available.
Automated gates, clean-environment drills, written decisions, and preserved
artifacts reduce dependence on memory and make a future handoff possible.

## Roles

One person may hold every role. When there is only one maintainer, that person
performs and records the single-maintainer continuity review described below.
An external review is welcome if a contributor becomes available, but it is not
a prerequisite for a release.

| Role | Decision owned | Evidence to leave |
|---|---|---|
| Scientific maintainer | Equations, parameter meaning, validation thresholds, and interpretation limits | Updated scientific tests, golden rationale, validation page, and review note |
| Software maintainer | Public API, configuration compatibility, architecture, and ordinary pull requests | Passing quick/full checks, migration note, and focused tests |
| Release maintainer | Version identity, clean tag, distributions, publication environments, and release notes | Completed release checklist, artifact hashes, and workflow links |
| Continuity check | Ability to repeat installation, tests, docs, and a dry-run release without undocumented knowledge | Dated release report or pull-request checklist with commands, results, and workflow links |

`CODEOWNERS` remains the machine-readable routing file. It should list the
people who actually maintain the corresponding paths. A project with one
maintainer should list one maintainer; do not add an account solely to create
the appearance of redundancy.

### Why continuity evidence matters for a single-maintainer project

Automated checks answer questions such as “do the tests pass?” They cannot show
that the repository explains how to obtain the data, choose the correct
command, interpret a scientific failure, or publish the intended artifact. A
project can therefore be technically green while depending on undocumented
knowledge held only in the maintainer's memory. This is often called a
**bus-factor risk**: work stops if that person is temporarily unavailable.

The absence of a second developer does not make a release invalid, and adding a
fictitious reviewer would not reduce this risk. For a single-maintainer project,
the practical safeguard is to reproduce the release from a fresh clone and a
clean environment, using only committed documentation, then preserve enough
evidence for the procedure to be audited and repeated later.

A single-maintainer continuity review follows these rules:

1. use a fresh clone outside the usual working copy and create a new virtual
   environment;
2. follow only the commands committed in the repository, without relying on an
   IDE state, global Python packages, or unpublished shell notes;
3. turn every missing prerequisite or ambiguous choice into a documentation or
   automation change, then repeat the affected check;
4. record the exact commit, commands, results, workflow links, artifact names,
   and remaining scientific limits in the release pull request or report;
5. keep tag creation and publication as separate deliberate actions after the
   recorded drill and protected-branch checks succeed.

## Continuity drill

The maintainer starts from a fresh clone and follows only repository documents:

1. complete {doc}`getting-started` and run `pyages new config quickstart`;
2. run `python -m scripts.maintenance.check_dev quick` and the standard tests;
3. build the Sphinx documentation with warnings treated as errors;
4. build a wheel and source archive, inspect them, and install the wheel in a
   clean environment;
5. follow {doc}`releasing` through the dry-run boundary without creating a
   production tag or publishing to a package index;
6. record every undocumented prerequisite or ambiguous decision as an issue.

The drill succeeds only if the maintainer can identify the generated result
manifest, explain which scientific checks are standard versus extensive, and
locate the exact version/citation update points without undocumented commands.
A failed drill is useful evidence: it identifies knowledge that must be written
down before the release process is reproducible.

## Change ownership map

| Change | Start here | Minimum focused evidence |
|---|---|---|
| YAML or CLI contract | `pyages/config/models.py`, `pyages/config/loading.py`, `pyages/cli/commands/` | schema, CLI, and workflow-path tests |
| Observation or LPM semantics | `pyages/concentrations/`, `pyages/lpm/`, `pyages/calibration/problem.py` | unit tests plus relevant analytical or golden qualification |
| MH or multi-chain behavior | `pyages/calibration/methods/mh/` | sampler/result tests and the applicable extensive qualification profiles |
| Result lifecycle or provenance | `pyages/workflows/runtime/manifest.py` | manifest, staging, failure, and quarantine tests |
| Installation or release | `pyproject.toml`, `install/`, `.github/workflows/` | metadata checker, clean distribution smoke test, and release checklist |
| Documentation | `docs/`, `README.md` | Sphinx warning-free HTML and link checks |

Review role coverage before each minor or major release and repeat the
continuity drill for that candidate. Repeat it at least annually or whenever the
release process, package layout, or maintainer changes.
