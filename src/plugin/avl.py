"""Pointer-based BST/AVL operations, shared input audit, and typed tree snapshots."""

from dataclasses import dataclass
from pathlib import Path

from contract import (
    NodeColor,
    NodeState,
    OperationKind,
    OperationStatus,
    OperationStep,
    Rotation,
    RotationKind,
    TreeInput,
    TreeKind,
    TreeOutput,
    TreeSnapshot,
)


@dataclass
class Node:
    key: int
    left: "Node | None" = None
    right: "Node | None" = None
    height: int = 1
    color: NodeColor | None = None


def height(node):
    return 0 if node is None else node.height


def refresh(node):
    node.height = 1 + max(height(node.left), height(node.right))
    return node


def balance(node):
    return height(node.left) - height(node.right)


def rotate(node, kind, trace):
    if kind == RotationKind.RIGHT:
        parent = node.left
        node.left = parent.right
        parent.right = refresh(node)
    else:
        parent = node.right
        node.right = parent.left
        parent.left = refresh(node)
    refresh(parent)
    trace.append(Rotation(kind, node.key, parent.key))
    return parent


def rebalance(node, trace, balanced=True):
    refresh(node)
    if not balanced:
        return node
    if balance(node) > 1:
        if balance(node.left) < 0:
            node.left = rotate(node.left, RotationKind.LEFT, trace)
        return rotate(node, RotationKind.RIGHT, trace)
    if balance(node) < -1:
        if balance(node.right) > 0:
            node.right = rotate(node.right, RotationKind.RIGHT, trace)
        return rotate(node, RotationKind.LEFT, trace)
    return node


def insert(node, key, trace, balanced=True):
    if node is None:
        return Node(key)
    if key == node.key:
        return node
    if key < node.key:
        node.left = insert(node.left, key, trace, balanced)
    else:
        node.right = insert(node.right, key, trace, balanced)
    return rebalance(node, trace, balanced)


def delete(node, key, trace, balanced=True):
    if node is None:
        return None
    if key < node.key:
        node.left = delete(node.left, key, trace, balanced)
    elif key > node.key:
        node.right = delete(node.right, key, trace, balanced)
    else:
        if node.left is None:
            return node.right
        if node.right is None:
            return node.left
        successor = node.right
        while successor.left is not None:
            successor = successor.left
        node.key = successor.key
        node.right = delete(node.right, successor.key, trace, balanced)
    return rebalance(node, trace, balanced)


def valid_key(key):
    if type(key) is not int or not -(2**31) <= key <= 2**31 - 1:
        raise ValueError("keys must be signed 32-bit integers")


def load(value):
    source = value.initial
    entries = [] if source is None else source.nodes
    root = None if source is None else source.root
    if len(entries) > 256 or len(value.operations) > 128:
        raise ValueError("at most 256 initial nodes and 128 operations are supported")
    links = {}
    for entry in entries:
        valid_key(entry.key)
        if entry.key in links:
            raise ValueError("duplicate initial node key")
        links[entry.key] = entry
    visited, black_heights = set(), {}

    def build(key, lower=None, upper=None):
        if key is None:
            return None
        valid_key(key)
        if key not in links or key in visited:
            raise ValueError("initial links must form one tree without cycles, shared children, or missing nodes")
        if (lower is not None and key <= lower) or (upper is not None and key >= upper):
            raise ValueError("initial tree violates binary search ordering")
        visited.add(key)
        entry = links[key]
        node = refresh(Node(key, build(entry.left, lower, key), build(entry.right, key, upper), color=entry.color))
        if value.tree_type == TreeKind.AVL and abs(balance(node)) > 1:
            raise ValueError("initial tree must already satisfy AVL balance")
        if value.tree_type == TreeKind.RED_BLACK:
            if node.color not in (NodeColor.RED, NodeColor.BLACK):
                raise ValueError("red-black nodes require explicit red/black colors")
            if node.right is not None and node.right.color == NodeColor.RED:
                raise ValueError("left-leaning red-black trees cannot have a red right link")
            if node.color == NodeColor.RED and node.left is not None and node.left.color == NodeColor.RED:
                raise ValueError("red-black trees cannot have consecutive red links")
            a, b = black_heights.get(entry.left, 0), black_heights.get(entry.right, 0)
            if a != b:
                raise ValueError("red-black paths must have equal black height")
            black_heights[key] = a + (node.color == NodeColor.BLACK)
        elif node.color is not None:
            raise ValueError("BST/AVL nodes must have color null")
        return node

    tree = build(root)
    if visited != set(links):
        raise ValueError("initial tree contains disconnected nodes")
    if value.tree_type == TreeKind.RED_BLACK and tree is not None and tree.color != NodeColor.BLACK:
        raise ValueError("red-black root must be black")
    keys = set(links)
    emitted = len(keys)
    for operation in value.operations:
        valid_key(operation.key)
        if operation.kind == OperationKind.INSERT:
            keys.add(operation.key)
        else:
            keys.discard(operation.key)
        emitted += len(keys)
        if len(keys) > 256 or emitted > 8192:
            raise ValueError("operation sequence exceeds 256 live nodes or 8192 total snapshot node entries")
    return tree


def snapshot(node):
    rows, ordered = [], []

    def walk(current):
        if current is None:
            return
        walk(current.left)
        ordered.append(current.key)
        rows.append(
            NodeState(
                current.key,
                None if current.left is None else current.left.key,
                None if current.right is None else current.right.key,
                current.height,
                balance(current),
                current.color,
            )
        )
        walk(current.right)

    walk(node)
    return TreeSnapshot(None if node is None else node.key, rows, ordered, height(node), len(rows))


def apply_operations(value: TreeInput, workspace: Path) -> TreeOutput:
    from .red_black import update

    root = load(value)
    initial = snapshot(root)
    members = set(initial.inorder)
    steps = []
    for operation in value.operations:
        trace, recolors = [], []
        existed = operation.key in members
        if operation.kind == OperationKind.INSERT:
            if not existed:
                root = (
                    update(root, operation, trace, recolors)
                    if value.tree_type == TreeKind.RED_BLACK
                    else insert(root, operation.key, trace, value.tree_type == TreeKind.AVL)
                )
            members.add(operation.key)
            status = OperationStatus.ALREADY_PRESENT if existed else OperationStatus.INSERTED
        else:
            if existed:
                root = (
                    update(root, operation, trace, recolors)
                    if value.tree_type == TreeKind.RED_BLACK
                    else delete(root, operation.key, trace, value.tree_type == TreeKind.AVL)
                )
            members.discard(operation.key)
            status = OperationStatus.DELETED if existed else OperationStatus.NOT_FOUND
        steps.append(OperationStep(operation, status, trace, snapshot(root), recolors))
    return TreeOutput(
        value, initial, steps, initial if not steps else steps[-1].tree, sum(len(step.rotations) for step in steps)
    )
