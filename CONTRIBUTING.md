# Contributing to PyAges

Contributions are welcome when their origin and licensing are clear.

By submitting a contribution, you confirm that you have the right to provide
it and agree that it may be distributed as part of PyAges under the CeCILL 2.1
licence. This is not a copyright assignment: contributors retain the rights
they hold in their own contributions unless a separate written agreement says
otherwise.

New source files must include, near the beginning of the file:

```text
Copyright (c) YEAR COPYRIGHT HOLDER
SPDX-License-Identifier: CECILL-2.1
```

Replace the placeholders with accurate information. Preserve existing
copyright, attribution, and licence notices when modifying a file. Do not copy
third-party code, data, figures, or documentation into the repository unless
its terms are compatible and its provenance and required notices are recorded.
Data additions must also update `NOTICE-DATA.md`; direct dependency changes
must update `THIRD_PARTY_NOTICES.md` and `install/constraints.txt` together.

Run the licensing check before submitting a change:

```console
python scripts/check_licensing.py
```

## Documentation

Documentation follows supported responsibilities and contracts rather than
mirroring every source directory. Read the [documentation scope and
granularity](docs/dev/documentation-scope.md) before adding a page. In
particular, user-visible configuration, CLI, output, scientific, and
compatibility changes must update the corresponding online reference; private
implementation details normally stay in docstrings, comments, and tests.

Build the documentation with warnings treated as errors:

```console
python -m sphinx -E -a -W --keep-going -b html docs docs/_build/html
```
