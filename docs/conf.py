from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pygments.lexers.special import TextLexer
from sphinx.highlighting import lexers

from pyage import __version__

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

project = "PyAge"
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

html_title = "PyAge documentation"
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")
html_show_sourcelink = False

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
