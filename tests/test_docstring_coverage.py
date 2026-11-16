"""The config schema carries the attribute docstrings the site generates from.

`test_verdance_config_fields_have_attribute_docstrings` is the one that matters
here: it pins the exact shape Griffe reads, so a field documented with a `#`
comment — which renders as nothing — cannot slip back in.

Coverage of everything the site renders is handled by
`tests/test_docs_consistency.py`, which derives its targets from the `:::`
directives rather than the hand-maintained list below.
"""

import ast
import pathlib

import pytest

RENDERED = [
    "config/schema.py", "config/loader.py", "t3.py", "t30.py", "t30_buildings.py",
    "t300.py", "tree_count.py", "merge.py", "pipeline.py", "osm.py", "overture.py",
    "terrain.py", "open_buildings.py", "api.py",
]


def _public(tree):
    return [
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")
    ]


@pytest.mark.parametrize("rel", RENDERED)
def test_public_objects_have_docstrings(rel):
    path = pathlib.Path("src/verdance") / rel
    tree = ast.parse(path.read_text())
    missing = [n.name for n in _public(tree) if not ast.get_docstring(n)]
    assert missing == [], f"{rel}: undocumented public objects {missing}"


def test_verdance_config_fields_have_attribute_docstrings():
    """Every VerdanceConfig field carries a string literal directly beneath it."""
    tree = ast.parse(pathlib.Path("src/verdance/config/schema.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "VerdanceConfig")
    undocumented = []
    for i, node in enumerate(cls.body):
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        nxt = cls.body[i + 1] if i + 1 < len(cls.body) else None
        documented = (
            isinstance(nxt, ast.Expr)
            and isinstance(nxt.value, ast.Constant)
            and isinstance(nxt.value.value, str)
        )
        if not documented:
            undocumented.append(node.target.id)
    assert undocumented == [], f"fields without attribute docstrings: {undocumented}"
