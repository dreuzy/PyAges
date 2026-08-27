# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pygments.lexers.special import TextLexer
from sphinx.highlighting import lexers

from pyages import __version__

DOCS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DOCS_ROOT.parent

# Autosummary pages are ignored build artifacts. Do not remove them while
# loading the configuration: Sphinx may reuse its environment during an
# incremental build and still need the generated sources. Clean release and CI
# builds start from a clean checkout; maintainers can use ``make clean`` when a
# removed API module leaves a stale local page.

project_metadata = tomllib.loads(
    (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
)["project"]

project = "PyAges"
author = ", ".join(
    author_data["name"] for author_data in project_metadata.get("authors", [])
)
release = __version__
version = release

root_doc = "index"
language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
]

source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
]
myst_heading_anchors = 3

# Keep Mermaid labels readable in the constrained Read the Docs content area.
# Diagrams can also be opened full-screen and zoomed/panned with the mouse.
mermaid_init_config = {
    "startOnLoad": False,
    "flowchart": {
        "curve": "linear",
        "nodeSpacing": 55,
        "rankSpacing": 65,
    },
    "themeVariables": {
        "fontSize": "18px",
    },
}
mermaid_d3_zoom = True
mermaid_fullscreen = True
mermaid_fullscreen_button_opacity = "90"
mermaid_height = "auto"

autosummary_generate = True
autosummary_imported_members = False
autosummary_ignore_module_all = False

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
}
autodoc_member_order = "bysource"
autodoc_mock_imports = [
    "IPython",
    "imageio",
]
autodoc_preserve_defaults = True
autodoc_typehints = "description"

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_use_ivar = True

html_title = "PyAges documentation"
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")
html_show_sourcelink = True
html_static_path = ["_static"]
html_css_files = ["css/readthedocs.css"]
html_js_files = ["js/mermaid-click-to-expand.js"]
github_version = os.environ.get("READTHEDOCS_GIT_COMMIT_HASH", "").strip() or "main"
html_context = {
    "display_github": True,
    "github_user": "dreuzy",
    "github_repo": "PyAges",
    "github_version": github_version,
    "conf_py_path": "/docs/",
}

# Some publishers and data registries resolve these valid DOI links for
# browsers but block or close automated checker requests. Keep every
# user-facing DOI while excluding only the known bot-blocked endpoints; all
# other external links remain checked. Retry transient failures before
# reporting them as broken.
linkcheck_timeout = 10
linkcheck_retries = 3
linkcheck_report_timeouts_as_broken = False
linkcheck_ignore = [
    r"https://hplus\.ore\.fr/en/ploemeur/",
    r"https://doi\.org/10\.1029/2000RG000101",
    r"https://doi\.org/10\.1029/2003WR002436",
    r"https://doi\.org/10\.1002/2013WR014012",
    r"https://doi\.org/10\.1029/2006WR005096",
    r"https://doi\.org/10\.15138/BVQ6-2S69",
    r"https://doi\.org/10\.15138/PJ63-H440",
    r"https://doi\.org/10\.15138/4N0D-4M07",
    r"https://doi\.org/10\.15138/TQ02-ZX42",
    r"https://doi\.org/10\.3133/tm4F3",
    r"https://pubs\.usgs\.gov/publication/tm4F3",
    r"https://pubs\.usgs\.gov/tm/4-f3/pdf/tm4-F3\.pdf",
]

lexers["csv"] = TextLexer()

try:
    import sphinx_rtd_theme  # noqa: F401
except ImportError:
    html_theme = "alabaster"
else:
    html_theme = "sphinx_rtd_theme"
    html_theme_options = {
        "collapse_navigation": False,
        "navigation_depth": 4,
    }


def _html_page_context(app, page_name, template_name, context, doctree) -> None:
    """Hide edit links whose autosummary source files are not versioned."""
    del app, template_name, doctree
    if page_name.startswith("api/generated/"):
        context["display_github"] = False


def setup(app):
    """Register documentation-only HTML context adjustments."""
    app.connect("html-page-context", _html_page_context)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
