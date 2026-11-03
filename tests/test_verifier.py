"""Hand-specified tree shapes, independent set invariants, and corrupted traces."""

import copy
import itertools
import json
import random
from dataclasses import replace
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import (
    InitialTree,
    NodeLinks,
    NodeState,
    OperationKind,
    OperationStatus,
    RotationKind,
    TreeInput,
    TreeKind,
    TreeOperation,
    TreeOutput,
    TreeSnapshot,
)
from plugin.avl import apply_operations

CASES = Path(__file__).parent / "cases"


def avl_input(initial, operations):
    return TreeInput(initial, operations, TreeKind.AVL)


def sample(name="insert-lr"):
    return build_output(json.loads((CASES / f"{name}.input.json").read_text()), TreeInput)


def audit(snapshot, members):
    rows = {row.key: row for row in snapshot.nodes}
    assert len(rows) == len(snapshot.nodes) == snapshot.size == len(members)
    seen = set()

    def walk(key, lower=None, upper=None):
        if key is None:
            return [], 0
        assert key in rows and key not in seen
        seen.add(key)
        assert lower is None or lower < key
        assert upper is None or key < upper
        node = rows[key]
        left, a = walk(node.left, lower, key)
        right, b = walk(node.right, key, upper)
        assert node.height == 1 + max(a, b) and node.balance == a - b and abs(a - b) <= 1
        return [*left, key, *right], node.height

    ordered, height = walk(snapshot.root)
    assert ordered == snapshot.inorder == sorted(members)
    assert height == snapshot.height and seen == set(members)


@pytest.mark.parametrize("path", sorted(CASES.glob("*.input.json")), ids=lambda path: path.stem)
def test_hand_specified_snapshots_and_rotations(path, tmp_path):
    given = build_output(json.loads(path.read_text()), TreeInput)
    before = copy.deepcopy(given)
    made = apply_operations(given, tmp_path)
    expected = json.loads(path.with_name(path.name.replace(".input.", ".expected.")).read_text())
    assert plain_output(made) == expected
    assert verifier.verify_input("apply_operations", given)["valid"]
    assert verifier.verify_output("apply_operations", given, made, "")["valid"]
    assert verifier.verify_task("tree-operations", given, made, None, "")["valid"]
    assert given == before and not list(tmp_path.iterdir())


@pytest.mark.parametrize("field", ["request", "initial", "steps", "final", "total_rotations"])
def test_every_result_field_is_checked(field, tmp_path):
    given = sample()
    made = apply_operations(given, tmp_path)
    wrong = {
        "request": replace(given, operations=[]),
        "initial": replace(made.initial, height=9),
        "steps": [],
        "final": replace(made.final, root=10),
        "total_rotations": made.total_rotations + 1,
    }
    result = verifier.verify_task("tree-operations", given, replace(made, **{field: wrong[field]}), None, "")
    assert not result["valid"] and result["score"] == 0


@pytest.mark.parametrize("field", ["root", "nodes", "inorder", "height", "size"])
def test_corrupt_snapshot_is_rejected_even_if_final_and_last_step_agree(field, tmp_path):
    given = sample()
    made = apply_operations(given, tmp_path)
    wrong = {"root": 30, "nodes": [], "inorder": [30, 20, 10], "height": 9, "size": 2}
    bad = replace(made.final, **{field: wrong[field]})
    steps = [*made.steps[:-1], replace(made.steps[-1], tree=bad)]
    assert not verifier.verify_task("tree-operations", given, replace(made, steps=steps, final=bad), None, "")["valid"]


@pytest.mark.parametrize("field", ["key", "left", "right", "height", "balance"])
def test_every_node_field_is_verified(field, tmp_path):
    given = sample()
    made = apply_operations(given, tmp_path)
    node = made.final.nodes[0]
    bad_node = replace(node, **{field: {"key": 999, "left": 999, "right": 999, "height": 99, "balance": 2}[field]})
    bad = replace(made.final, nodes=[bad_node, *made.final.nodes[1:]])
    forged = replace(made, final=bad, steps=[*made.steps[:-1], replace(made.steps[-1], tree=bad)])
    assert not verifier.verify_task("tree-operations", given, forged, None, "")["valid"]


@pytest.mark.parametrize("mutation", ["missing", "reordered", "direction", "pivot", "new_root", "status", "operation"])
def test_rotation_trace_and_status_forgery_fails(mutation, tmp_path):
    given = sample()
    made = apply_operations(given, tmp_path)
    step = made.steps[-1]
    rotations = list(step.rotations)
    if mutation == "missing":
        rotations = []
    elif mutation == "reordered":
        rotations.reverse()
    elif mutation == "direction":
        rotations[0] = replace(rotations[0], kind=RotationKind.RIGHT)
    elif mutation == "pivot":
        rotations[0] = replace(rotations[0], pivot=999)
    elif mutation == "new_root":
        rotations[0] = replace(rotations[0], new_root=999)
    step = replace(step, rotations=rotations)
    if mutation == "status":
        step = replace(step, status=OperationStatus.ALREADY_PRESENT)
    if mutation == "operation":
        step = replace(step, operation=TreeOperation(OperationKind.DELETE, 20))
    assert not verifier.verify_task("tree-operations", given, replace(made, steps=[*made.steps[:-1], step]), None, "")[
        "valid"
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        "cycle",
        "shared",
        "missing_child",
        "disconnected",
        "bad_global_order",
        "unbalanced",
        "duplicate",
        "root_missing",
        "empty_root",
        "key_range",
        "operation_range",
    ],
)
def test_invalid_starting_trees_are_rejected(mutation, tmp_path):
    given = sample("delete-leaf")
    raw = plain_output(given)
    nodes = raw["initial"]["nodes"]
    rows = {row["key"]: row for row in nodes}
    if mutation == "cycle":
        rows[20]["left"] = 20
    elif mutation == "shared":
        rows[30]["left"] = 10
    elif mutation == "missing_child":
        rows[10]["left"] = 5
    elif mutation == "disconnected":
        nodes.append({"key": 99, "left": None, "right": None})
    elif mutation == "bad_global_order":
        rows[10]["right"] = 25
        nodes.append({"key": 25, "left": None, "right": None})
    elif mutation == "unbalanced":
        raw["initial"] = {
            "root": 3,
            "nodes": [
                {"key": 3, "left": 2, "right": None},
                {"key": 2, "left": 1, "right": None},
                {"key": 1, "left": None, "right": None},
            ],
        }
    elif mutation == "duplicate":
        nodes.append(copy.deepcopy(nodes[0]))
    elif mutation == "root_missing":
        raw["initial"]["root"] = 999
    elif mutation == "empty_root":
        raw["initial"]["root"] = None
    elif mutation == "key_range":
        nodes[0]["key"] = 2**31
    else:
        raw["operations"][0]["key"] = -(2**31) - 1
    for node in raw["initial"]["nodes"]:
        node.setdefault("color", None)
    given = build_output(raw, TreeInput)
    assert not verifier.verify_input("apply_operations", given)["valid"]
    with pytest.raises(ValueError):
        apply_operations(given, tmp_path)


def test_576_complete_small_insert_delete_histories(tmp_path):
    for insertion in itertools.permutations(range(4)):
        for deletion in itertools.permutations(range(4)):
            operations = [TreeOperation(OperationKind.INSERT, key) for key in insertion] + [
                TreeOperation(OperationKind.DELETE, key) for key in deletion
            ]
            given = avl_input(None, operations)
            made = apply_operations(given, tmp_path)
            assert made.final.root is None and made.final.size == 0
            assert verifier.verify_task("tree-operations", given, made, None, "")["valid"]
            members = set()
            for step in made.steps:
                if step.operation.kind == OperationKind.INSERT:
                    members.add(step.operation.key)
                else:
                    members.discard(step.operation.key)
                audit(step.tree, members)


def test_mixed_sequences_against_set_model_and_independent_replay(tmp_path):
    generator = random.Random(480)
    for _ in range(64):
        operations = [
            TreeOperation(generator.choice(list(OperationKind)), generator.randrange(-24, 25)) for _ in range(64)
        ]
        given = avl_input(None, operations)
        made = apply_operations(given, tmp_path)
        assert verifier.verify_task("tree-operations", given, made, None, "")["valid"]
        members = set()
        for step in made.steps:
            existed = step.operation.key in members
            if step.operation.kind == OperationKind.INSERT:
                members.add(step.operation.key)
                assert step.status == (OperationStatus.ALREADY_PRESENT if existed else OperationStatus.INSERTED)
            else:
                members.discard(step.operation.key)
                assert step.status == (OperationStatus.DELETED if existed else OperationStatus.NOT_FOUND)
            audit(step.tree, members)


def initial_tree(keys):
    nodes = []

    def build(items):
        if not items:
            return None
        midpoint = len(items) // 2
        key = items[midpoint]
        nodes.append(NodeLinks(key, build(items[:midpoint]), build(items[midpoint + 1 :]), None))
        return key

    return InitialTree(build(keys), nodes)


def test_bounds_and_snapshot_budget(tmp_path):
    given = avl_input(initial_tree(list(range(256))), [])
    made = apply_operations(given, tmp_path)
    assert made.final.size == 256 and verifier.verify_task("tree-operations", given, made, None, "")["valid"]
    cases = [
        avl_input(initial_tree(list(range(257))), []),
        avl_input(None, [TreeOperation(OperationKind.INSERT, 1)] * 129),
    ]
    at_limit = avl_input(initial_tree(list(range(64))), [TreeOperation(OperationKind.INSERT, 0)] * 127)
    assert verifier.verify_task("tree-operations", at_limit, apply_operations(at_limit, tmp_path), None, "")["valid"]
    cases.append(replace(at_limit, operations=[TreeOperation(OperationKind.INSERT, 0)] * 128))
    for bad in cases:
        assert not verifier.verify_input("apply_operations", bad)["valid"]
        with pytest.raises(ValueError):
            apply_operations(bad, tmp_path)


def test_operation_order_matters_but_initial_node_table_order_does_not(tmp_path):
    a = avl_input(None, [TreeOperation(OperationKind.INSERT, key) for key in [1, 2, 3, 4]])
    b = avl_input(None, list(reversed(a.operations)))
    first, second = apply_operations(a, tmp_path), apply_operations(b, tmp_path)
    assert first.final.inorder == second.final.inorder == [1, 2, 3, 4]
    assert first.final.root == 2 and second.final.root == 3
    given = sample("delete-cascade")
    alternate = replace(given, initial=replace(given.initial, nodes=list(reversed(given.initial.nodes))))
    assert apply_operations(given, tmp_path).final == apply_operations(alternate, tmp_path).final


def test_schema_and_missing_output(tmp_path):
    with pytest.raises((ValueError, TypeError)):
        build_output({"initial": None}, TreeInput)
    raw = {"initial": None, "operations": [{"kind": "rotate", "key": 1}]}
    with pytest.raises((ValueError, TypeError)):
        build_output(raw, TreeInput)
    given = sample()
    made = apply_operations(given, tmp_path)
    malformed = plain_output(made)
    malformed["total_rotations"] = "two"
    with pytest.raises((ValueError, TypeError)):
        build_output(malformed, TreeOutput)
    assert not verifier.verify_task("tree-operations", given, None, None, "")["valid"]
    assert not verifier.verify_input("unknown", given)["valid"]


def test_a_balanced_predecessor_result_is_not_the_declared_successor_result(tmp_path):
    given = sample("delete-two-children")
    made = apply_operations(given, tmp_path)
    alternative = TreeSnapshot(
        30,
        [
            NodeState(10, None, 25, 2, -1, None),
            NodeState(25, None, None, 1, 0, None),
            NodeState(30, 10, 40, 3, 1, None),
            NodeState(40, None, None, 1, 0, None),
        ],
        [10, 25, 30, 40],
        3,
        4,
    )
    audit(alternative, {10, 25, 30, 40})
    forged = replace(made, final=alternative, steps=[replace(made.steps[0], tree=alternative)])
    assert not verifier.verify_task("tree-operations", given, forged, None, "")["valid"]
