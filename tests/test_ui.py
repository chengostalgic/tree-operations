"""Check tree diagrams and user-visible status/rotation messages through the kit interface."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KIT = """
export const h = (tag, attrs = {}, ...children) => ({tag, attrs, children});
export const statusPill = (text) => h("span", {text});
export const disclosure = (options, ...children) => h("details", {}, options.summary, children);
export const dataTable = ({columns, rows}) => ({element: h("table", {}, rows.map(row => columns.map(column => row[column.key])))});
"""
DRAW = """
import {readFileSync} from "node:fs";
import renderers from "./renderers.mjs";
const sample = JSON.parse(readFileSync("sample.json", "utf8"));
const verdict = JSON.parse(readFileSync("verdict.json", "utf8"));
function text(node) {
  if (node == null || node === false) return "";
  if (Array.isArray(node)) return node.map(text).join(" ");
  if (typeof node !== "object") return String(node);
  return (node.attrs?.text ?? "") + " " + text(node.children);
}
console.log(text(renderers.TreeOutput(sample, {verdict})));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="renderer smoke test needs Node")
@pytest.mark.parametrize(
    "name,valid,words",
    [
        ("insert-lr", True, "Rotate left at 10; new subtree root 20"),
        ("delete-cascade", True, "Rotate right at 11; new subtree root 10"),
        ("duplicate-and-missing", True, "Already present; unchanged"),
        ("empty", True, "Empty tree ∅"),
        ("inspect-zero-root", True, "No operations requested"),
        ("insert-ll", False, "Verification failed"),
        ("bst-skewed", True, "Unbalanced BST operations complete"),
        ("rb-single", True, "Recolor 10: red → black"),
        ("rb-delete-black-leaf", True, "Left-leaning red-black (2–3)"),
    ],
)
def test_tree_card(name, valid, words, tmp_path):
    sample = json.loads((ROOT / "tests/cases" / f"{name}.expected.json").read_text())
    source = (ROOT / "ui/renderers.js").read_text().replace("./kit/components.js", "./components.mjs")
    for filename, content in [
        ("renderers.mjs", source),
        ("components.mjs", KIT),
        ("draw.mjs", DRAW),
        ("sample.json", json.dumps(sample)),
        ("verdict.json", json.dumps({"valid": valid, "message": "valid" if valid else "bad tree"})),
    ]:
        (tmp_path / filename).write_text(content)
    result = subprocess.run(["node", "draw.mjs"], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert words in result.stdout
    if valid:
        assert "Final nodes, heights, balances and colors" in result.stdout
    else:
        assert "AVL operations complete" not in result.stdout
