# Maintainership and continuity

PyAges has automated technical gates, but release and scientific judgement must
remain transferable between people. The current `CODEOWNERS` file names one
account for every area, so it documents responsibility but does not yet provide
operational backup. This page defines the evidence required to close that gap.

## Roles

One person may hold several roles, but a public release needs a second person
capable of performing the continuity review independently.

| Role | Decision owned | Evidence to leave |
|---|---|---|
| Scientific maintainer | Equations, parameter meaning, validation thresholds, and interpretation limits | Updated scientific tests, golden rationale, validation page, and review note |
| Software maintainer | Public API, configuration compatibility, architecture, and ordinary pull requests | Passing quick/full checks, migration note, and focused tests |
| Release maintainer | Version identity, clean tag, distributions, publication environments, and release notes | Completed release checklist, artifact hashes, and workflow links |
| Continuity reviewer | Ability to repeat installation, tests, docs, and a dry-run release without private knowledge | Dated handoff-drill issue or pull-request review |

`CODEOWNERS` remains the machine-readable routing file. Add the continuity
reviewer's GitHub identity there once that person has completed the drill; do
not add an account solely to make the file appear redundant.

### Why a second person matters

Automated checks answer questions such as “do the tests pass?” They cannot show
that another person understands how to obtain the data, choose the correct
command, interpret a scientific failure, or publish the intended artifact. A
project can therefore be technically green while depending on undocumented
knowledge held by one maintainer. This is often called a **bus-factor risk**:
work stops if that one person is temporarily unavailable.

The continuity reviewer is not merely a second name on an approval rule. The
reviewer should be able to start from an empty machine, notice missing
instructions, and explain what each release check establishes. The useful
outcome is a reproducible handoff, not an administrative checkbox.

A practical way to introduce this role is:

1. choose a contributor who did not prepare the release candidate;
2. give that person only the repository URL and the documented prerequisites;
3. let the person follow the drill below without private messages or copied
   shell history;
4. turn every question that required oral help into a documentation change;
5. record the successful drill in an issue or pull request, then add the
   reviewer to `CODEOWNERS`.

## Continuity drill

The reviewer starts from a fresh clone and follows only repository documents:

1. complete {doc}`getting-started` and run `pyages new config quickstart`;
2. run `python -m scripts.maintenance.check_dev quick` and the standard tests;
3. build the Sphinx documentation with warnings treated as errors;
4. build a wheel and source archive, inspect them, and install the wheel in a
   clean environment;
5. follow {doc}`releasing` through the dry-run and TestPyPI boundary without
   creating a production tag or publishing to PyPI;
6. record every undocumented prerequisite or ambiguous decision as an issue.

The drill succeeds only if the reviewer can identify the generated result
manifest, explain which scientific checks are standard versus extensive, and
locate the exact version/citation update points without help from the primary
maintainer. A failed drill is useful evidence: it identifies knowledge that
must be written down before the release process is truly transferable.

## Change ownership map

| Change | Start here | Minimum focused evidence |
|---|---|---|
| YAML or CLI contract | `pyages/config/models.py`, `pyages/config/loading.py`, `pyages/cli/commands/` | schema, CLI, and workflow-path tests |
| Observation or LPM semantics | `pyages/concentrations/`, `pyages/lpm/`, `pyages/calibration/problem.py` | unit tests plus relevant analytical or golden qualification |
| MH or multi-chain behavior | `pyages/calibration/methods/mh/` | sampler/result tests and the applicable extensive qualification profiles |
| Result lifecycle or provenance | `pyages/workflows/runtime/manifest.py` | manifest, staging, failure, and quarantine tests |
| Installation or release | `pyproject.toml`, `install/`, `.github/workflows/` | metadata checker, clean distribution smoke test, and release checklist |
| Documentation | `docs/`, `README.md` | Sphinx warning-free HTML and link checks |

Review role coverage before each minor release and repeat the continuity drill
at least annually or whenever the release process, package layout, or primary
maintainer changes.
