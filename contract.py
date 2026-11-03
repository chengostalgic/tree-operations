"""Bounded BST, AVL, and left-leaning red-black set operations with full traces."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    APPLY_OPERATIONS = "apply_operations"


class Task(Enum):
    TREE_OPERATIONS = "tree-operations"


class TreeKind(Enum):
    BST = "bst"
    AVL = "avl"
    RED_BLACK = "red_black"


class NodeColor(Enum):
    RED = "red"
    BLACK = "black"


class OperationKind(Enum):
    INSERT = "insert"
    DELETE = "delete"


class OperationStatus(Enum):
    INSERTED = "inserted"
    DELETED = "deleted"
    ALREADY_PRESENT = "already_present"
    NOT_FOUND = "not_found"


class RotationKind(Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass
class NodeLinks(Output):
    key: Annotated[int, "Unique signed 32-bit integer key"]
    left: Annotated[int | None, "Left child's key, or null"]
    right: Annotated[int | None, "Right child's key, or null"]
    color: Annotated[NodeColor | None, "red/black required for red_black; null required for bst/avl"]


@dataclass
class InitialTree(Output):
    root: int | None
    nodes: Annotated[list[NodeLinks], "All nodes of one valid tree of the selected type; row order has no effect"]


@dataclass
class TreeOperation(Output):
    kind: OperationKind
    key: int


@dataclass
class TreeInput(Output):
    initial: Annotated[
        InitialTree | None,
        "null means start empty. If a specific existing tree is supplied, preserve its exact child links. "
        "An unordered key set does not determine its shape; ask if shape or insertion order is ambiguous.",
    ]
    operations: Annotated[
        list[TreeOperation],
        "0 to 128 insert/delete operations in the user's exact sequence. To build from an insertion sequence, "
        "start empty and include those inserts first. Never sort or deduplicate the operation sequence.",
    ]
    tree_type: Annotated[
        TreeKind,
        "bst = unbalanced search tree; avl = height-balanced (default choice when unspecified); "
        "red_black = left-leaning 2-3 red-black variant, not arbitrary textbook variants. "
        "Always supply this field. Preserve the previous type for follow-ups; never silently convert a tree.",
    ]


@dataclass
class NodeState(Output):
    key: int
    left: int | None
    right: int | None
    height: Annotated[int, "Empty subtree height 0, leaf height 1"]
    balance: Annotated[int, "Left height minus right height; restricted to -1, 0, 1 only for AVL"]
    color: NodeColor | None


@dataclass
class TreeSnapshot(Output):
    root: int | None
    nodes: Annotated[list[NodeState], "Every node once, sorted by key"]
    inorder: Annotated[list[int], "Strictly increasing keys in the tree"]
    height: int
    size: int


@dataclass
class Rotation(Output):
    kind: RotationKind
    pivot: Annotated[int, "Subtree root immediately before this primitive rotation"]
    new_root: Annotated[int, "Subtree root immediately after it"]


@dataclass
class Recolor(Output):
    key: int
    before: NodeColor
    after: NodeColor


@dataclass
class OperationStep(Output):
    operation: TreeOperation
    status: OperationStatus
    rotations: Annotated[list[Rotation], "Primitive rotations in execution order; double rotations have two entries"]
    tree: TreeSnapshot
    recolors: Annotated[
        list[Recolor],
        "Actual color changes in execution order, including root normalization; empty for BST/AVL. "
        "Fresh red-node creation is not a recolor. Rotations have their own ordered trace.",
    ]


@dataclass
class TreeOutput(Output):
    request: TreeInput
    initial: TreeSnapshot
    steps: list[OperationStep]
    final: TreeSnapshot
    total_rotations: int


TOOLS = {Tool.APPLY_OPERATIONS: (TreeInput, TreeOutput)}
TASKS = {Task.TREE_OPERATIONS: (TreeInput, TreeOutput)}
