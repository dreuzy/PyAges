# GitHub migration

GitHub is the canonical host for new PyAges changes, pull requests, checks, and
future releases. The GitLab repository is retained and is not closed by this
migration. Maintainers must avoid pushing divergent development to both hosts.

The canonical repository name is ``PyAges`` and its path component is
``pyages``. The canonical GitHub URL is
``https://github.com/dreuzy/PyAges``. The retained GitLab mirror must use
``https://gitlab.com/dreuzy/pyages`` once its project path has been renamed.

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
project is connected through the Read the Docs GitHub App. Its legacy
``pyage-gw`` slug remains live and supported. Read the Docs does not provide a
self-service project-slug rename: request a supported rename and redirects
from ``support@readthedocs.org`` if a ``pyages``-based URL is required. Do not
delete and recreate the project, because that would break existing inbound
links. Update `pyproject.toml`, the repository homepage, and documentation
links only after Read the Docs confirms the new slug and its redirects and the
renamed site has completed its first successful public build.
