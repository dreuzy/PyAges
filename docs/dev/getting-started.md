# Developer quickstart

This guide takes you from a new copy of PyAges to a first checked change. It is
written for contributors who are still learning the Python development tools
used by the project. You do not need to memorize the commands: each section
explains what they do and why they are useful.

PyAges supports Python 3.12 through 3.14. Python 3.12 is the version normally
used for local development and for building the documentation.

## Before you start

The commands below are entered in a **terminal** (also called a shell):
PowerShell on Windows, or a terminal application on macOS and Linux. A line
starting with `python`, `git`, or `pyages` is a command to run; do not copy the
triple backticks surrounding the examples.

You will meet these terms throughout the guide:

- A **repository** is the directory containing the project source code and its
  history.
- A **virtual environment** is a private Python installation for one project.
  It prevents PyAges dependencies from interfering with other Python projects.
- A **dependency** is a package that PyAges needs in order to run, test, or
  build documentation.
- The **CLI** (command-line interface) is the `pyages` command used from a
  terminal.

### The whole process at a glance

The actions below do not all need to be repeated at the same frequency:

| Action | When to do it | What it changes |
| --- | --- | --- |
| Clone the repository | Once per computer or working copy | Creates a local `pyages/` directory and its Git history. |
| Create the virtual environment | Once per working copy | Creates `.venv/`, containing a private Python and private installed packages. |
| Activate the environment | At the start of each new terminal session | Changes command lookup in that terminal only; it does not change source files. |
| Install the project | After creating the environment, and again when dependencies change | Installs dependencies and the `pyages` command inside `.venv/`. |
| Create a branch | Once per contribution | Gives the work its own Git history without changing the main branch. |
| Edit and run focused tests | Repeatedly while developing | Changes working files; tests read and execute them but normally do not edit them. |
| Run the full check | Once the change appears complete | Verifies the complete contribution locally; it does not upload anything. |

This distinction is important: creating, activating, and installing an
environment are three separate actions. Creation makes the directory,
activation selects it for the current terminal, and installation puts PyAges
and its dependencies inside it.

## 1. Copy the project and create its environment

This is normally a one-time setup action. It creates files on your computer but
does not change anything on GitHub.

Run these commands from the directory in which you want to keep the project:

```bash
git clone https://github.com/dreuzy/PyAges.git pyages
cd pyages
python -m venv .venv
```

Here is what each command means:

- `git clone ... pyages` downloads a working copy of the repository into a
  directory named `pyages`. It also creates the hidden `.git/` directory that
  stores version history and remembers the GitHub repository as `origin`.
- `cd pyages` makes that new directory the current working directory.
- `python -m venv .venv` asks Python to create a virtual environment in the
  hidden `.venv` directory. `-m venv` means “run Python's built-in `venv`
  module.” This creates an empty environment; it does not install PyAges yet.

Activate the environment on PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

Activation tells the terminal to use the environment's `python`, `pip`, and
`pyages` programs. Most terminals show `(.venv)` at the start of the prompt
after activation. You normally activate the environment again whenever you
open a new terminal for this project.

Activation only adjusts the current terminal's command search path. Closing
the terminal removes that adjustment; deleting or changing project files is
not involved. Run `deactivate` if you want to leave the environment without
closing the terminal.

## 2. Install PyAges and the development tools

Run:

```bash
python -m pip install --upgrade -r install/bootstrap-constraints.txt
python -m pip install -c install/constraints.txt -e ".[dev]"
```

The first command installs the project-qualified packaging tools:

- `pip` finds, resolves, downloads, and installs Python packages;
- `setuptools` reads the project metadata and prepares PyAges for installation
  or distribution;
- `wheel` supports Python's standard built-package format;
- `-r install/bootstrap-constraints.txt` asks `pip` to install the exact
  versions listed in that file;
- `--upgrade` replaces older copies already present in `.venv` when needed.

The second command installs PyAges and the normal developer dependencies. Each
part has a purpose:

- `python -m pip` runs the package installer belonging to the currently
  selected Python. This avoids accidentally using `pip` from another Python
  installation.
- `install` asks `pip` to install packages.
- `-c install/constraints.txt` uses versions that the project has already
  tested together.
- `-e .` installs the current directory in **editable** mode. A change made in
  the source files is then immediately used without reinstalling PyAges.
- `[dev]` installs the optional developer tools, including Pytest, Ruff, and
  Pyright. The quotation marks make the command work consistently across
  shells.

Behind the scenes, `pip` reads `pyproject.toml` to learn which packages PyAges
needs, chooses versions allowed by the constraints file, downloads anything
missing, and installs it under `.venv/`. It also creates the `pyages` terminal
command. Editable mode stores a link to this working copy, so importing
`pyages` uses the files you are editing rather than a separate frozen copy.

You normally rerun these installation commands only when `pyproject.toml`, one
of the constraints files, or the requested extras change. Editing an ordinary
`.py` file does not require reinstallation because the project is editable.

Now check the installation:

```bash
python -m pip check
python -m scripts.maintenance.check_project_metadata --check-installed --extra dev
python -c "import sys; print(sys.executable)"
pyages --version
pyages check
```

The commands answer five different questions. A successful command returns to
the prompt without an error; a failed command exits with a non-zero status and
prints the reason.

| Command | Question it answers | Evidence of success |
| --- | --- | --- |
| `python -m pip check` | Are the installed package versions compatible with one another? | It prints `No broken requirements found.` |
| `python -m scripts.maintenance.check_project_metadata ...` | Do project declarations, qualified pins, and the selected installed groups agree? | It reports internally consistent metadata and compatible direct dependencies. |
| `python -c "..."` | Which Python executable is this terminal actually using? | The printed path contains `.venv`. |
| `pyages --version` | Was the PyAges CLI installed and can the terminal find it? | It prints a PyAges version. |
| `pyages check` | Can PyAges find the project resources it needs at runtime? | Its individual checks are reported as successful. |

If PowerShell policy prevents activation, you can address the environment's
executables directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade -r install/bootstrap-constraints.txt
.\.venv\Scripts\python.exe -m pip install -c install/constraints.txt -e ".[dev]"
.\.venv\Scripts\pyages.exe check
```

Do not treat a successful `import pyages` from the repository root as proof of
installation: Python can import the checkout merely because the current
directory contains it. The `pyages --version` check also proves that the CLI
entry point was installed.

## 3. Add optional tools only when needed

An **extra** is a named group of optional dependencies. The `dev` extra is
enough for normal code and test work. Install one of the following larger
groups only when the change needs it:

```bash
# Documentation work: adds Sphinx and its extensions
python -m pip install -c install/constraints.txt -e ".[dev,docs]"

# Notebooks and spreadsheet-backed examples
python -m pip install -c install/constraints.txt -e ".[dev,examples]"

# Work spanning both areas
python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"
```

Installing another extra adds packages to the same `.venv/`; it does not create
a second environment or enable a mode inside PyAges. For example, `docs` adds
Sphinx because building the website needs packages that running PyAges does not.
See {doc}`dependencies` for the difference between a compatibility range, an
exact qualified pin, and a package actually installed in this environment.

## 4. Make and check one change

Create a branch before editing:

```bash
git switch -c fix/short-description
```

This command has two actions: `-c` creates a branch named
`fix/short-description`, and `switch` makes it the current branch. New commits
will belong to this branch. Nothing is uploaded to GitHub at this point.

Consult the {doc}`code-tour`, make a small edit, and run the tests closest to
the code you changed. For example:

```bash
python -m pytest -q tests/data_io tests/lpm
python -m scripts.maintenance.check_dev quick
```

- `python -m pytest` starts **Pytest**, the program that executes automated
  tests. `-q` requests shorter output, and the two paths limit the run to the
  data-input and LPM tests.
- `python -m scripts.maintenance.check_dev quick` runs the project's fast group
  of developer checks. Running it through `python -m` guarantees that the
  script uses the active virtual environment.

Choose test paths related to your change; the table in the {doc}`code-tour`
provides examples. A focused test run is useful because it gives feedback more
quickly than the entire suite.

Pytest first **collects** test functions, normally those whose names begin with
`test_`. It then imports the code, runs each test, and evaluates its assertions.
An assertion states an expected result. In quiet output, a dot usually means a
test passed and `F` means an assertion failed. `E` means the test could not be
completed, often because setup or an import raised an unexpected exception.
The summary at the end names the failing test and shows the relevant call
stack. Pytest reads the working files directly, so a change does not have to be
committed before it can be tested.

### What the quick checks do

The `quick` command is a project **wrapper**: a small script that starts several
other tools in the correct order. It prints the current step, runs it, and stops
at the first failure. Later steps have not run when that happens. Fix the named
failure and launch the wrapper again. The wrapper checks the files but does not
automatically rewrite them.

| Check | Meaning and purpose |
| --- | --- |
| Dependency check | Detects installed packages whose version requirements contradict one another. |
| Ruff lint | **Ruff** reads Python without running it and detects likely mistakes, unused imports, and violations of the project's coding rules. This is called *linting*. |
| Ruff format | Verifies that layout, spacing, and line wrapping follow one consistent style. This avoids review discussions about formatting. |
| Pyright | **Pyright** compares type annotations with how values are used. It can catch, for example, code that may pass `None` where a number is required. |
| Docstring check | Verifies selected documentation written directly inside Python functions, classes, and modules. Such in-code documentation is called a *docstring*. |
| License check | Confirms that source files carry the required licence information. |
| Architecture check | Prevents imports that would make the main package layers depend on each other in unsupported directions. |

The quick profile normally finishes in seconds or tens of seconds. It
complements focused tests: Ruff and Pyright inspect code, while Pytest actually
runs examples and checks their results.

### Understanding Ruff's two actions

Ruff is used twice because finding suspicious code and arranging code are
different jobs:

```bash
python -m ruff check .
python -m ruff format --check .
```

In both commands, `.` means “start at the current directory and inspect the
project below it.” `ruff check` applies lint rules. A message such as
`path.py:10:5 F841 ...` identifies the file, line, column, rule code, and
explanation. Search for the rule code in the Ruff documentation only if the
explanation is insufficient.

`ruff format --check` calculates how Ruff would lay out the files but does not
write the result because of `--check`. To ask Ruff to perform the formatting,
run:

```bash
python -m ruff format .
```

Formatting may change spacing and line wrapping, so review the resulting diff.
It does not prove that the program behaves correctly; run Pytest as well. Ruff
can also apply some mechanical lint fixes with `python -m ruff check . --fix`.
Use that option deliberately and review every change rather than assuming an
automatic edit is semantically correct.

### Understanding Pyright's action

Pyright does not execute the scientific calculations. It follows the type
information through the configured part of the source tree and asks whether
each operation is compatible with that information. For example, adding a
number to a value annotated as `str`, or using an optional value without first
checking for `None`, produces a diagnostic. The usual command is:

```bash
python -m pyright
```

Its output points to the file and expression it could not prove safe. A
Pyright error may reveal either a real bug or incomplete type information; the
appropriate response is to understand which case applies, not simply to hide
the warning.

Pyright was introduced progressively in PyAges. Its guaranteed scope now
contains the whole installed package (`pyages/`), every executable example
helper (`examples/`), the maintained site studies (`sites/`), the TracerLPM
validation code (`validation/`), and the shared and maintenance tools under
`scripts/common/` and `scripts/maintenance/`, plus the article, scientific
qualification, and release tooling under `scripts/article/`,
`scripts/qualification/`, and `scripts/release/`. The `[tool.pyright]` `include` list in
`pyproject.toml` records that boundary. The usual command checks this whole
maintained surface:

```bash
python -m pyright
```

Because directories are listed rather than individual files, a new Python
module below any of them is checked automatically. This prevents a newly added
article or release script from silently falling outside the type check. The
gate was expanded only after every existing diagnostic had been understood and
corrected; no broad ignore was used to admit these directories.

The direct whole-package audit is also green:

```bash
python -m pyright pyages
```

Both commands currently report zero errors. The first is the daily maintained-
surface check; the second is useful when a developer wants to isolate the
installed package.

A diagnostic is not automatically a runtime bug. For example, pandas can
return several related container types and its type definitions may be wider
than the value PyAges actually expects. The correction may be a more precise
local annotation or an explicit validation boundary. Other diagnostics, such
as accessing an attribute on a possible `None`, a missing return path, or a
possibly uninitialized variable, can expose a real failure path. Each message
must therefore be understood before it is corrected or suppressed.

When correcting a diagnostic, follow the value back to the boundary that
establishes its type. For a pandas column, for example, PyAges verifies that the
selection really is one `Series` before applying numeric operations. Avoid a
broad `ignore` merely to obtain green output: it removes the protection without
clarifying the runtime contract. After changing a type boundary, run the nearby
Pytest tests as well, because Pyright reads code but does not execute the
scientific calculation.

### The everyday edit-and-check loop

Development is normally a short repeated loop rather than one large edit:

1. Make one logically small source or documentation change.
2. Run the closest Pytest test or build the page concerned.
3. Read the failure, if any, and correct the cause.
4. Run `check_dev quick` before considering that small change ready.
5. Inspect `git diff` to see exactly what changed.

`git diff` is read-only: it compares working files with the last committed
version and does not save, discard, or upload anything. This review often finds
accidental edits that automated tools cannot recognize.

## 5. Run the complete check before review

Before opening a pull request, install the `docs` extra and run:

```bash
python -m scripts.maintenance.check_dev full
```

The `full` profile repeats the quick checks and also:

- confirms that the documented test list matches the tests Pytest currently
  discovers;
- runs the standard test suite (more than 1,500 cases);
- asks **Sphinx**, the documentation builder, to build every page and treat
  broken links or other warnings as errors.

It normally takes several minutes. The separate `extensive` scientific tests
may take hours, so they are required only for certain numerical changes. The
{doc}`testing` guide explains when to run them.

The full check uses the files currently present in the working directory. They
do not have to be committed, and the command does not commit or upload them. A
successful run means that this local state satisfies the checks; GitHub's CI
will repeat them after the branch is pushed.

If you add, remove, move, parametrize, or change a marker on a test, first
regenerate the committed test inventory:

```bash
python -m scripts.maintenance.generate_test_inventory
```

The inventory is a generated documentation page that records how many tests
exist in each category. Regenerating it keeps that page synchronized with the
test suite.

## When a command fails

A failed check is information about one specific requirement, not a sign that
the whole setup is unusable. Start with the last named check and the final error
message. It usually contains a file path and line number. Fix that issue, run
the focused command again, and then return to `check_dev`.

Different failures point to different layers:

| First useful clue | Likely meaning | First action |
| --- | --- | --- |
| `command not found` or “not recognized” | The virtual environment is not active, or the tool was not installed. | Check the Python path and repeat the installation step if needed. |
| `No module named ...` | The selected Python cannot see a required package. | Confirm that `.venv` is selected and that the appropriate extra was installed. |
| A Ruff rule code | A particular source line violates a lint or formatting rule. | Read the message at that line; use an automatic fix only after understanding it. |
| A Pyright diagnostic | The annotated types and a possible use of a value disagree. | Follow the reported value back to where its type is established. |
| `FAILED` from Pytest | The code ran, but an observed result differed from an assertion. | Read the expected and actual values, then decide whether code or test expectation is wrong. |
| `ERROR` from Pytest | The test could not reach its assertion. | Start with the first project frame in the traceback, often an import or setup problem. |
| A Sphinx warning | A documentation page, directive, or reference cannot be built cleanly. | Open the named document and correct the referenced line or target. |

Common first checks are:

- confirm that the terminal prompt contains `(.venv)` or that the printed
  Python path contains `.venv`;
- confirm that the command is being run from the repository root (the directory
  containing `pyproject.toml`);
- rerun the installation command if a module or executable is missing;
- use the failure's file path to choose a smaller Pytest command while fixing a
  test.

## Where to go next

- {doc}`code-tour` follows execution from a YAML configuration file to the
  scientific calculation and suggests tests for common changes.
- {doc}`ide` configures interpreter discovery, tests, and debugging in an
  editor.
- {doc}`testing` explains standard, extensive, coverage, validation, and
  reference-result test groups.
- {doc}`../architecture` records which parts of the program may depend on one
  another.
- {doc}`contributing` explains the repository-wide review policy.
