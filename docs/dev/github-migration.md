# GitHub migration

GitHub is the canonical host for new PyAges changes, pull requests, checks, and
future releases. The GitLab repository is retained and is not closed by this
migration. Maintainers must avoid pushing divergent development to both hosts.

## Access model

The GitHub repository is public for reading. Public users may open issues,
participate in discussions, fork the project, and propose pull requests, but
they have no permission to push, force-push, delete branches or tags, change
settings, or publish releases. Maintainer and automation permissions follow
least privilege; ordinary workflows receive read-only repository contents.

## Migrated and non-migrated state

Git commits, branches, and the historical tag were copied. Provider-specific
objects such as GitLab issues, merge-request discussions, variables, webhooks,
permissions, and CI logs are not Git objects and are not implicitly migrated.
They remain part of the GitLab record unless separately inventoried.

## Public-history review

The current tree excludes local outputs and third-party publisher files, but
older reachable commits contain generated results, publisher PDFs, a local
presentation, and a historical `.env`. The `.env` value inspected during the
migration contained only `PYTHONPATH`; this does not replace a complete secret
scan. Before broad redistribution of repository history, review those objects
for licensing, privacy, and secrets.

History is not rewritten automatically because scientific manifests record
commit identities. If an object must be removed, preserve the original history
in a controlled archive and document how old provenance identifiers map to the
new public history.

## Documentation hosting

The Read the Docs configuration remains in `.readthedocs.yaml`. The public
project must be imported through the Read the Docs GitHub App under an
available project slug, such as `pyages`. Add the live documentation
URL to `pyproject.toml`, the repository homepage, and README only after the
first successful public build.
