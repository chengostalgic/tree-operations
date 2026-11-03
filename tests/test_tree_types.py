"""Type-specific invariants, exact color traces, continuation, and cross-policy checks."""

import copy
import itertools
import random
from dataclasses import replace

import pytest

import verifier
from contract import (
    InitialTree,
    NodeColor,
    NodeLinks,
    OperationKind,
    TreeInput,
    TreeKind,
    TreeOperation,
)
from plugin import apply_operations


def request(tree_type, inserts=(), deletes=(), initial=None):
    return TreeInput(
        initial,
        [TreeOperation(OperationKind.INSERT, key) for key in inserts]
        + [TreeOperation(OperationKind.DELETE, key) for key in deletes],
        tree_type,
    )


def audit(tree, members, kind):
    """Independent test oracle: set semantics plus structural/type invariants, no operation algorithm."""
    nodes = {node.key: node for node in tree.nodes}
    seen = set()

    def visit(key, lo=None, hi=None):
        if key is None:
            return [], 0, 0
        assert key not in seen and key in nodes
        assert (lo is None or lo < key) and (hi is None or key < hi)
        seen.add(key)
        node = nodes[key]
        a, ah, ab = visit(node.left, lo, key)
        b, bh, bb = visit(node.right, key, hi)
        assert node.height == 1 + max(ah, bh) and node.balance == ah - bh
        if kind == TreeKind.AVL:
            assert abs(ah - bh) <= 1
        if kind == TreeKind.RED_BLACK:
            assert node.color in (NodeColor.RED, NodeColor.BLACK)
            assert node.right is None or nodes[node.right].color == NodeColor.BLACK
            if node.color == NodeColor.RED:
                assert node.left is None or nodes[node.left].color == NodeColor.BLACK
            assert ab == bb
        else:
            assert node.color is None
        return [*a, key, *b], node.height, ab + (node.color == NodeColor.BLACK)

    ordered, height, _ = visit(tree.root)
    assert ordered == tree.inorder == sorted(members)
    assert seen == set(members) and tree.size == len(members) and tree.height == height
    if tree.root is not None and kind == TreeKind.RED_BLACK:
        assert nodes[tree.root].color == NodeColor.BLACK


def check_history(given, tmp_path):
    before = copy.deepcopy(given)
    made = apply_operations(given, tmp_path)
    assert given == before
    assert verifier.verify_input("apply_operations", given)["valid"]
    assert verifier.verify_task("tree-operations", given, made, None, "")["valid"]
    members = set(made.initial.inorder)
    audit(made.initial, members, given.tree_type)
    for step in made.steps:
        existed = step.operation.key in members
        if step.operation.kind == OperationKind.INSERT:
            members.add(step.operation.key)
        else:
            members.discard(step.operation.key)
        audit(step.tree, members, given.tree_type)
        if given.tree_type == TreeKind.BST:
            assert step.rotations == []
        if given.tree_type != TreeKind.RED_BLACK:
            assert step.recolors == []
        if (step.operation.kind == OperationKind.INSERT and existed) or (
            step.operation.kind == OperationKind.DELETE and not existed
        ):
            assert step.rotations == step.recolors == []
    return made


@pytest.mark.parametrize("kind", [TreeKind.BST, TreeKind.RED_BLACK])
def test_all_576_four_key_insertion_deletion_histories(kind, tmp_path):
    for inserts in itertools.permutations(range(4)):
        for deletes in itertools.permutations(range(4)):
            assert check_history(request(kind, inserts, deletes), tmp_path).final.size == 0


@pytest.mark.parametrize("kind", [TreeKind.BST, TreeKind.RED_BLACK])
def test_64_seeded_mixed_histories(kind, tmp_path):
    rng = random.Random(580)
    for _ in range(64):
        given = TreeInput(
            None, [TreeOperation(rng.choice(list(OperationKind)), rng.randrange(-24, 25)) for _ in range(64)], kind
        )
        check_history(given, tmp_path)


@pytest.mark.parametrize("kind", list(TreeKind))
def test_sorted_sequence_and_full_delete(kind, tmp_path):
    check_history(request(kind, range(64), reversed(range(64))), tmp_path)


@pytest.mark.parametrize("kind", list(TreeKind))
def test_continuation_preserves_type_shape_and_colors(kind, tmp_path):
    one = check_history(request(kind, [9, 3, 12, 1, 5, 10, 14, 0, 2]), tmp_path)
    initial = InitialTree(one.final.root, [NodeLinks(n.key, n.left, n.right, n.color) for n in one.final.nodes])
    continuation = check_history(request(kind, [6, 4], [9, 0, 14], initial), tmp_path)
    combined = check_history(request(kind, [9, 3, 12, 1, 5, 10, 14, 0, 2, 6, 4], [9, 0, 14]), tmp_path)
    assert continuation.final == combined.final
    assert continuation.steps == combined.steps[-5:]


def test_policy_is_part_of_verified_request(tmp_path):
    plain = request(TreeKind.BST, [30, 20, 10])
    avl = replace(plain, tree_type=TreeKind.AVL)
    rb = replace(plain, tree_type=TreeKind.RED_BLACK)
    p, a, r = (check_history(v, tmp_path) for v in [plain, avl, rb])
    assert p.final.root == 30 and a.final.root == r.final.root == 20
    assert p.total_rotations == 0 and a.total_rotations == r.total_rotations == 1
    assert all(n.color is None for n in a.final.nodes)
    assert all(n.color == NodeColor.BLACK for n in r.final.nodes)
    assert not verifier.verify_task("tree-operations", plain, a, None, "")["valid"]
    assert not verifier.verify_task("tree-operations", avl, r, None, "")["valid"]
    forged = replace(a, request=replace(avl, tree_type=TreeKind.BST))
    assert not verifier.verify_task("tree-operations", avl, forged, None, "")["valid"]


@pytest.mark.parametrize("mutation", ["root_red", "red_right", "consecutive_red", "black_height", "missing_color"])
def test_invalid_llrb_starts(mutation, tmp_path):
    B, R = NodeColor.BLACK, NodeColor.RED
    cases = {
        "root_red": InitialTree(1, [NodeLinks(1, None, None, R)]),
        "red_right": InitialTree(1, [NodeLinks(1, None, 2, B), NodeLinks(2, None, None, R)]),
        "consecutive_red": InitialTree(
            3, [NodeLinks(3, 2, None, B), NodeLinks(2, 1, None, R), NodeLinks(1, None, None, R)]
        ),
        "black_height": InitialTree(2, [NodeLinks(2, 1, None, B), NodeLinks(1, None, None, B)]),
        "missing_color": InitialTree(1, [NodeLinks(1, None, None, None)]),
    }
    given = request(TreeKind.RED_BLACK, initial=cases[mutation])
    assert not verifier.verify_input("apply_operations", given)["valid"]
    with pytest.raises(ValueError):
        apply_operations(given, tmp_path)


@pytest.mark.parametrize("kind", [TreeKind.AVL, TreeKind.BST])
def test_non_rb_color_is_rejected(kind, tmp_path):
    given = request(kind, initial=InitialTree(1, [NodeLinks(1, None, None, NodeColor.BLACK)]))
    assert not verifier.verify_input("apply_operations", given)["valid"]
    with pytest.raises(ValueError):
        apply_operations(given, tmp_path)


def test_valid_llrb_may_have_balance_greater_than_one(tmp_path):
    B, R = NodeColor.BLACK, NodeColor.RED
    initial = InitialTree(
        8,
        [
            NodeLinks(8, 4, 10, B),
            NodeLinks(4, 2, 6, R),
            NodeLinks(2, 1, None, B),
            NodeLinks(1, None, None, R),
            NodeLinks(6, 5, None, B),
            NodeLinks(5, None, None, R),
            NodeLinks(10, None, None, B),
        ],
    )
    given = request(TreeKind.RED_BLACK, initial=initial)
    made = check_history(given, tmp_path)
    assert next(n for n in made.final.nodes if n.key == 8).balance == 2
    wrong_type = replace(
        given, tree_type=TreeKind.AVL, initial=replace(initial, nodes=[replace(n, color=None) for n in initial.nodes])
    )
    assert not verifier.verify_input("apply_operations", wrong_type)["valid"]
    check_history(request(TreeKind.RED_BLACK, [7, 11], [8, 1, 10], initial), tmp_path)


def test_degenerate_256_node_bst_and_deep_successor_deletion(tmp_path):
    initial = InitialTree(0, [NodeLinks(k, None, k + 1 if k < 255 else None, None) for k in range(256)])
    made = check_history(request(TreeKind.BST, deletes=[0, 128, 255], initial=initial), tmp_path)
    assert made.initial.height == 256 and made.final.height == 253 and made.total_rotations == 0


def test_full_black_255_node_red_black_start_and_large_updates(tmp_path):
    nodes = []

    def build(low, high):
        if low >= high:
            return None
        key = (low + high) // 2
        nodes.append(NodeLinks(key, build(low, key), build(key + 1, high), NodeColor.BLACK))
        return key

    initial = InitialTree(build(0, 255), nodes)
    made = check_history(
        request(TreeKind.RED_BLACK, inserts=[255], deletes=[127, 0, 255, *range(1, 20)], initial=initial), tmp_path
    )
    assert made.steps[0].tree.size == 256 and made.final.size == 234


@pytest.mark.parametrize("mutation", ["node_color", "missing_recolors", "reordered_recolors", "key", "before", "after"])
def test_forged_rb_color_and_trace_fails(mutation, tmp_path):
    given = request(TreeKind.RED_BLACK, [20, 10, 30])
    made = apply_operations(given, tmp_path)
    step = made.steps[-1]
    if mutation == "node_color":
        bad = replace(made.final, nodes=[replace(made.final.nodes[0], color=NodeColor.RED), *made.final.nodes[1:]])
        forged = replace(made, final=bad, steps=[*made.steps[:-1], replace(step, tree=bad)])
    else:
        recolors = list(step.recolors)
        if mutation == "missing_recolors":
            recolors = []
        elif mutation == "reordered_recolors":
            recolors.reverse()
        else:
            wrong = {"key": 999, "before": NodeColor.RED, "after": NodeColor.BLACK}[mutation]
            recolors[0] = replace(recolors[0], **{mutation: wrong})
        forged = replace(made, steps=[*made.steps[:-1], replace(step, recolors=recolors)])
    assert not verifier.verify_task("tree-operations", given, forged, None, "")["valid"]
