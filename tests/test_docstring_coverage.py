"""The public surface the documentation site renders must carry docstrings.

mkdocstrings renders whatever it finds; a function with no docstring becomes a
bare signature on the site, which is worse than no API page. These tests pin
the modules `docs/api/` and `docs/configuration.md` render, so a new public
function cannot reach the site undocumented.
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
