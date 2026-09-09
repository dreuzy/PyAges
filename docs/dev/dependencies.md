# Understanding and maintaining dependencies

A Python project rarely runs alone. It relies on other packages for numerical
work, configuration, tests, documentation, and packaging. Those packages are
called **dependencies**. This page explains where PyAges declares them, why the
same package can appear in several files, and how to check an environment
without having to guess what each command proves.

## The four layers

PyAges separates four questions that are easy to confuse:

| Layer | File | Question answered |
| --- | --- | --- |
| Compatibility | `pyproject.toml` | Which versions should PyAges be able to work with? |
| Qualified direct versions | `install/constraints.txt` | Which direct runtime and optional versions has the project selected and tested together? |
| Packaging tools | `install/bootstrap-constraints.txt` | Which versions of `pip`, `setuptools`, and `wheel` prepare and build the environment? |
| Historical reproduction | `install/environment.yml` | Which direct Conda environment reproduces the archived article campaign? |

An installed environment is a fifth, local reality: it is the set of packages
currently present inside your `.venv`. It can drift from the files above if it
was created earlier or if a package was installed manually.

### Compatible is not the same as qualified

A declaration such as `click>=8.1,<9` in `pyproject.toml` is a **compatibility
range**. It tells `pip` that any matching Click release may be selected. This is
important for users who install PyAges alongside other software.

A line such as `click==8.5.0` in `install/constraints.txt` is a **pin**: `==`
selects one exact release. Contributors use the pins so that a failure is less
likely to depend on which day the environment was installed.

The qualified version does not have to be the newest published version. A new
release is first reviewed and tested, especially when it affects numerical
results. “Newer exists” is therefore information for maintainers, not proof
that the current pin is wrong.

### A constraints file is not a complete lock file

`install/constraints.txt` pins PyAges' **direct** dependencies: packages named
by this project. Those packages can themselves install **transitive**
dependencies, which the file does not all pin. The final transitive selection
can differ by operating system or Python version.

The file therefore provides a shared qualified baseline, not a bit-for-bit
reconstruction of every package in every environment. Use `python -m pip list`
when you need to record what one concrete environment actually contains.

## Create the normal developer environment

After creating and activating `.venv`, run both commands from the repository
root:

```bash
python -m pip install --upgrade -r install/bootstrap-constraints.txt
python -m pip install -c install/constraints.txt -e ".[dev]"
```

The first command prepares the installer and build tools:

- `--upgrade` replaces an older installed version when necessary;
- `-r` means “install the requirements listed in this file”;
- `pip` resolves and installs packages;
- `setuptools` turns the source metadata into an installable Python project;
- `wheel` supports the standard built-distribution format.

The second command installs PyAges and its direct dependencies:

- `-c` means “constrain packages to the versions in this file”; unlike `-r`,
  it does not by itself request that every listed package be installed;
- `-e .` links the installation to the current source directory, so ordinary
  Python edits are visible immediately;
- `[dev]` requests the optional tools used for testing and code checks.

Add `docs` for documentation work and `examples` for notebooks or spreadsheets:

```bash
python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"
```

## Check what is installed

Start with the normal, compatibility-level checks:

```bash
python -m pip check
python -m scripts.maintenance.check_project_metadata --check-installed --extra dev
```

`pip check` inspects the complete installed dependency graph. It detects, for
example, that package A requires package B 2.x while B 1.x is installed. It
does not compare the environment with PyAges' qualified pins.

The metadata command performs the project-specific checks. It verifies that:

- every direct dependency has a qualified pin;
- each pin is inside the compatibility range for Python 3.12, 3.13, and 3.14;
- the selected runtime and `dev` dependencies are installed and compatible;
- packaging, documentation, Conda, and project metadata still agree.

To reproduce the stricter CI dependency audit, install all extras and require
the exact qualified versions:

```bash
python -m scripts.maintenance.check_project_metadata \
  --check-installed --extra dev --extra docs --extra examples \
  --require-qualified-versions
python -m pip_audit --local --skip-editable
```

`pip-audit` compares installed third-party versions with published security
advisories. `--local` audits this environment rather than resolving a new one.
`--skip-editable` skips the editable PyAges checkout, whose local source has no
published package record to audit. A clean result means no known advisory was
found in the data consulted; it is not a general proof that the software has no
security defect.

## Understand the historical Conda environment

`install/environment.yml` serves a narrower purpose: reproducing the historical
article campaign on Python 3.12. Its older direct versions are deliberate
scientific provenance. Do not synchronize that file automatically with the
normal developer pins.

The command below installs PyAges without allowing `pip` to replace the Conda
packages:

```bash
python -m pip install --no-deps -e .
```

Here, `--no-deps` means “install this project but do not resolve or install its
dependencies.” It is appropriate only because Conda has already created the
recorded environment.

## Qualify a dependency update

Dependabot groups proposed updates by purpose, and the scheduled dependency
audit reports newer releases once a week. Neither mechanism merges or changes
the pins by itself. A maintainer reviews an update as follows:

1. Read the package's release notes and security information. Identify removed
   APIs, changed defaults, supported Python versions, and numerical changes.
2. Change the relevant direct pin in `install/constraints.txt`. Update
   `install/bootstrap-constraints.txt` instead for `pip`, `setuptools`, or
   `wheel`.
3. Update the qualification date in the changed constraints file. The Git
   commit containing the file is the permanent source revision.
4. Create a fresh virtual environment and install the qualified bootstrap,
   runtime, and optional groups. A fresh environment prevents an old package
   from hiding a missing declaration.
5. Run the exact metadata check, `pip check`, `pip-audit`, focused tests, and
   `python -m scripts.maintenance.check_dev full`.
6. Let the clean CI matrix test Python 3.12, 3.13, and 3.14. Run the extensive
   scientific qualification when a scientific or numerical dependency can
   affect results.
7. Describe the reviewed release notes, checks, and any observed numerical
   effect in the pull request.

Do not widen a compatibility range merely because a new pin exists. The range
is a promise to users and should change only when that broader compatibility
has evidence. Conversely, testing only one exact pin does not prove every
release allowed by a wide range; lower-bound and compatibility jobs provide
additional evidence where the distinction matters.

The qualified direct and bootstrap baselines were last reviewed on
2026-09-06. The constraints files, CI result, and pull-request discussion are
the maintainable record of that review.
