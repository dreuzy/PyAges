# Contributing to PyAges

PyAges welcomes bug reports, documentation improvements, tests, and changes to
the software or its scientific methods. You do not need to be familiar with all
of the project before contributing. A small, well-explained change with focused
tests is a good first contribution.

Changes are proposed through a **pull request** (often shortened to PR) on
GitHub. A pull request lets maintainers read the change, discuss it, and run the
automated checks before merging it into the project. Public users can propose
changes but cannot directly modify or delete repository content.

## Development setup

PyAges supports Python 3.12 through 3.14. The commands in this section create a
local copy of the project and a private Python environment for it:

```bash
git clone https://github.com/dreuzy/PyAges.git pyages
cd pyages
python -m venv .venv
```

- `git clone` downloads the repository and its version history.
- `cd pyages` moves the terminal into the downloaded directory.
- `python -m venv .venv` creates a **virtual environment**: an isolated Python
  installation whose packages will not affect other projects.

Activate the environment on PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

Then install PyAges and the normal contributor tools:

```bash
python -m pip install --upgrade -r install/bootstrap-constraints.txt
python -m pip install -c install/constraints.txt -e ".[dev]"
python -m pip check
python -m scripts.maintenance.check_project_metadata --check-installed --extra dev
pyages --version
pyages check
```

The first installation command selects the tested versions of `pip`,
`setuptools`, and `wheel`: the tools that install and package Python projects.
The second command uses `-c install/constraints.txt` to select application and
developer versions tested by PyAges. `-e .` connects the installation to the
source directory so edits take effect immediately, and `[dev]` adds tools used
to test and inspect the code.

The final four commands verify different parts of the setup: a consistent
package graph, agreement with PyAges' declarations, an installed `pyages`
command, and accessible PyAges resources.
See the [developer quickstart](docs/dev/getting-started.md) for a command-by-
command explanation, an activation-free PowerShell fallback, and help with
common failures. The [dependency guide](docs/dev/dependencies.md) explains why
compatible ranges, qualified pins, installed versions, and the historical
Conda environment are deliberately distinct.

Some dependencies are optional. Add `docs` when editing documentation and add
`examples` only for notebooks or spreadsheet-backed examples:

```bash
python -m pip install -c install/constraints.txt -e ".[dev,docs]"
python -m pip install -c install/constraints.txt -e ".[dev,examples]"
```

The [code tour](docs/dev/code-tour.md) maps common changes to their source files
and tests. Editor setup is documented in [docs/dev/ide.md](docs/dev/ide.md).

## Making a first contribution

The contribution process moves a change through several states:

```text
working files -> staged selection -> local commit -> branch on GitHub
              -> pull request -> reviewed change in the main branch
```

These states are intentionally separate. Editing a file does not automatically
put it in a commit; committing does not upload it; pushing does not merge it.
This separation gives you a chance to inspect the change at every stage. An
editor's Git interface may use buttons instead of commands, but it performs the
same actions.

### 1. Create and select a branch

Create a branch for one coherent change:

```bash
git switch -c fix/short-description
```

A branch is an independent line of local history. `-c` creates it and `switch`
selects it, so later commits are recorded there rather than on `main`. Replace
`fix/short-description` with a short name that describes the change. This
action does not yet create a commit or contact GitHub.

### 2. Edit and test in small steps

Make a small edit, save the file, and run tests for the area concerned. For
example:

```bash
python -m pytest -q tests/data_io tests/lpm
```

`pytest` executes automated examples and verifies their results. `-q` means
“quiet”: it keeps successful output short. The directory names limit this
example to data-input and LPM tests; choose directories related to your own
change. Tests use saved working files immediately; there is no need to stage or
commit first.

When the focused tests pass, run:

```bash
python -m scripts.maintenance.check_dev quick
```

`check_dev quick` groups the fast project-wide checks behind one command. It
does not replace the focused Pytest run because the tools look for different
kinds of problems. Repeat the edit, focused-test, and quick-check cycle until
the behaviour and checks agree.

### 3. Review exactly what changed

Before recording the change, inspect the working tree:

```bash
git status --short
git diff
```

`git status --short` lists modified, deleted, and new files. `git diff` shows
the changed lines in files Git already knows about. Both commands are
read-only. Confirm that every listed file belongs to the contribution and that
debug prints, generated outputs, credentials, and unrelated edits are absent.

New, **untracked** files appear in `git status` but not in an ordinary
`git diff`; open or diff them separately before selecting them.

### 4. Select and record a coherent snapshot

Select only the files that belong in the next commit:

```bash
git add path/to/changed_file.py path/to/related_test.py
git diff --staged
git commit -m "Explain the change briefly"
```

`git add` copies the current version of the named files into Git's **staging
area**. The staging area is a proposed snapshot; it is not an upload and it does
not make later edits disappear. `git diff --staged` reviews that exact snapshot.
`git commit` then records it in the current branch with a message explaining
its purpose.

If one file contains unrelated edits, do not stage the whole file blindly. Use
your editor's line or hunk staging support to select only the relevant parts.

### 5. Share the branch and open a pull request

After the required checks pass, upload the branch:

```bash
git push -u origin fix/short-description
```

`origin` is the short name Git assigned to the GitHub repository during
`clone`. `push` copies local commits to a branch on GitHub. `-u` remembers the
connection between the local and remote branches, so later updates usually need
only `git push`.

Pushing still does not modify `main`. Open a pull request on GitHub to propose
that the branch be reviewed and merged. The pull request shows the diff, starts
continuous-integration checks, and provides a place for review discussion.

## What the development checks protect

These tool names can be unfamiliar on a first Python project:

| Tool or check | What it reads or runs | What a failure asks you to investigate |
| --- | --- | --- |
| Pytest | Imports the project, runs test cases, and compares actual results with expected results. | Behaviour changed, an expectation is outdated, or test setup failed. |
| Dependency metadata check | Compares project declarations, qualified pins, documentation installation, and selected packages in the current environment. | A dependency is missing, incompatible, unqualified, or described inconsistently. |
| Ruff lint | Reads Python source without running it and applies named rules. This inspection is called *linting*. | A likely mistake, unused import, unclear construct, or project rule at the reported line. |
| Ruff format | Calculates the project's standard spacing, indentation, and line wrapping. | A file's layout differs from the common style; `ruff format .` can rewrite it. |
| Pyright | Follows values through the configured code and compares their uses with type annotations. | A value may have a different type from the one an operation requires. |
| Docstring check | Reads selected explanatory text stored inside Python modules, classes, and functions. | Required in-code documentation is absent or does not identify its object clearly. |
| Licence check | Reads file headers and project metadata. | Required ownership or reuse information is missing or inconsistent. |
| Architecture check | Parses imports between the main package layers. | A new dependency points in an unsupported direction or creates unwanted coupling. |
| Sphinx | Parses every documentation page and resolves its internal references while building HTML. | A page contains invalid markup, a broken reference, or another documentation warning. |

The quick profile runs the dependency, Ruff, Pyright, docstring, licence, and
architecture checks. It normally finishes in seconds or tens of seconds and
does not rewrite files automatically.

Each successful tool proves only one property. Ruff formatting success says
that layout is consistent, not that a calculation is correct. Pytest success
says that the cases exercised by the tests behaved as expected, not that all
possible inputs were tested. The checks are combined because their evidence is
complementary.

The commands used by `check_dev quick` are read-only. In particular,
`ruff format --check` reports a difference without changing the file. The
[developer quickstart](docs/dev/getting-started.md) shows the separate commands
that deliberately apply Ruff formatting or safe mechanical fixes.

## When to run which action

| Moment | Action | Purpose |
| --- | --- | --- |
| After a small edit | Run the closest Pytest file or directory. | Shorten the time between introducing a defect and seeing it. |
| Before recording a commit | Run `check_dev quick` and inspect `git diff`. | Catch broad static issues and accidental changes. |
| After changing the set or markers of tests | Regenerate the test inventory. | Keep the documented test counts synchronized. |
| Before pushing the finished contribution | Run `check_dev full`. | Exercise the standard suite and documentation from the complete working state. |
| After a relevant scientific or validation change | Run the corresponding `extensive` or `validation` profile. | Produce evidence for slower numerical or infrastructure contracts. |
| After opening the pull request | Read the CI result on GitHub. | Confirm that the committed and pushed state also works in clean supported environments. |

## Required checks before a pull request

Install the `docs` extra if necessary, then run the complete local contributor
gate:

```bash
python -m scripts.maintenance.check_dev full
```

Here, **gate** means an ordered set of conditions that must all pass before the
change is considered ready for review. The command checks the working files on
your computer. It does not stage, commit, push, or otherwise change their Git
state.

The `full` profile repeats the quick checks, verifies the generated test
inventory, runs the standard test suite, and performs a clean Sphinx build. It
normally takes several minutes. If a step fails, read the last named check and
its final error first; the message usually identifies the relevant file and
line.

After the pull request is opened, **continuous integration** (CI) runs these
checks again on GitHub in a clean environment. CI protects against differences
between one contributor's computer and the supported project environments.
CI sees only commits that were pushed. It cannot see an unsaved, unstaged, or
uncommitted fix that exists only on your computer.

The [testing guide](https://pyage-gw.readthedocs.io/en/latest/dev/testing.html)
explains the standard, extensive, coverage, TracerLPM, collection, and golden
test groups. The [continuous-integration reference](https://pyage-gw.readthedocs.io/en/latest/dev/ci.html)
maps every GitHub Actions job to its local command, trigger, and saved result.

Changes to the validation infrastructure should also run:

```bash
python run_tests.py validation
```

Changes affecting long scientific calculations should run:

```bash
python run_tests.py extensive
```

The extensive group is kept separate because it may take hours. Some of these
tests compare calculations with **golden values**: reviewed reference results
stored by the project. If a numerical change alters those values, explain why
the new result is scientifically correct; do not simply replace the reference
to make the test pass.

After adding, moving, parametrizing, or changing a marker on tests, regenerate
the committed inventory before running the full profile:

```bash
python -m scripts.maintenance.generate_test_inventory
```

The inventory is a generated documentation page that records the available
test categories and counts. Keeping it committed makes unexpected changes to
the suite visible during review.

## Scientific and data changes

- Explain changes to equations, parameterizations, tolerances, prior
  distributions, random seeds, or numerical outputs. A reviewer must be able to
  tell whether a difference is intended.
- Update tests, scientific documentation, and reproducibility manifests
  together when the behaviour they describe changes.
- Do not commit generated result directories, local runner configurations,
  credentials, personal data, or third-party publications without an explicit
  redistribution review.
- Preserve source attribution and transformation notes for every dataset so a
  future contributor can understand where it came from and how it was changed.

## Describing the pull request

Keep each pull request focused on one coherent change. Its description should
state:

- the problem or motivation;
- the approach taken;
- the commands used to validate the change;
- any effect on numerical results, datasets, public interfaces, or
  reproducibility.

All changes are reviewed through GitHub. By contributing, you agree that your
contribution is distributed under the repository's CeCILL 2.1 licence and that
you have the right to submit any included code, text, or data.
