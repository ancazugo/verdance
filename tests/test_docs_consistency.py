"""Static checks on the documentation sources.

These run without mkdocs installed, so they guard the docs from the normal test
suite and from CI's test job. Each one pins a failure that actually shipped:

* an unbalanced code fence silently swallows a config example into a paragraph;
* a ``markdown`` attribute without the ``md_in_html`` extension makes the
  wrapped markdown render as literal source text on the page;
* a ``:::`` directive pointed at an object with no docstring renders as a bare
  signature, which is worse than leaving it out.
"""

import ast
import pathlib
import re

import pytest

DOCS = pathlib.Path("docs")
SRC = pathlib.Path("src")
# Internal design documents, not part of the published site (mkdocs excludes them).
PAGES = sorted(p for p in DOCS.rglob("*.md") if "superpowers" not in p.parts)
DIRECTIVE = re.compile(r"^::: ([A-Za-z_][\w.]*)", re.M)


def _fence_count(text: str) -> int:
    return sum(1 for line in text.split("\n") if line.lstrip().startswith("```"))


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p))
def test_code_fences_are_balanced(page):
    """An odd number of ``` markers means a fence was never closed."""
    assert _fence_count(page.read_text()) % 2 == 0, f"{page}: unclosed code fence"


def test_md_in_html_enabled_if_any_page_uses_it():
    """A `markdown` attribute on an HTML block needs the md_in_html extension.

    Without it the wrapped markdown is emitted verbatim, so images and links
    inside the block appear as raw source on the rendered page.
    """
    users = [p for p in PAGES if re.search(r"<\w+[^>]*\smarkdown[\s>]", p.read_text())]
    if not users:
        pytest.skip("no page uses a markdown attribute")
    config = pathlib.Path("mkdocs.yml").read_text()
    assert "md_in_html" in config, (
        f"{[str(p) for p in users]} use a `markdown` attribute, but mkdocs.yml does not "
        "enable the md_in_html extension — their contents render as literal text"
    )


def _resolve(target: str):
    """Map a mkdocstrings target to (module file, object path) using the source tree."""
    parts = target.split(".")
    for cut in range(len(parts), 0, -1):
        stem = pathlib.Path(*parts[:cut])
        for candidate in (SRC / stem.with_suffix(".py"), SRC / stem / "__init__.py"):
            if candidate.exists():
                return candidate, parts[cut:]
    return None, []


def _documented_targets():
    """Every object the site renders, as (page, target) pairs."""
    for page in PAGES:
        for target in DIRECTIVE.findall(page.read_text()):
            yield page, target


@pytest.mark.parametrize(
    "page,target",
    list(_documented_targets()),
    ids=lambda v: v if isinstance(v, str) else str(v),
)
def test_rendered_objects_have_docstrings(page, target):
    """Everything behind a ::: directive renders its docstring, so it needs one."""
    path, attr = _resolve(target)
    assert path is not None, f"{page}: ::: {target} resolves to no file under src/"
    tree = ast.parse(path.read_text())

    if attr:
        node = next(
            (
                n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.name == attr[-1]
            ),
            None,
        )
        assert node is not None, f"{page}: ::: {target} names nothing in {path}"
        assert ast.get_docstring(node), f"{page}: ::: {target} has no docstring"
        return

    # A whole module: the module itself and every public object it renders.
    assert ast.get_docstring(tree), f"{page}: ::: {target} — {path} has no module docstring"
    missing = [
        n.name for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not n.name.startswith("_")
        and not ast.get_docstring(n)
    ]
    assert missing == [], f"{page}: ::: {target} renders undocumented objects {missing}"
