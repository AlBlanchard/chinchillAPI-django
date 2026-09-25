"""Documentation indépendante du runtime Django et des secrets de production."""

project = "ChinchillAPI"
author = "ChinchillAPI"
language = "fr"
extensions = ["myst_parser", "sphinxcontrib.mermaid"]
source_suffix = {".md": "markdown"}
root_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "sphinx_rtd_theme"
html_title = "ChinchillAPI — documentation technique"
html_theme_options = {"navigation_depth": 3}
myst_fence_as_directive = ["mermaid"]
mermaid_version = "11.12.0"
nitpicky = True
