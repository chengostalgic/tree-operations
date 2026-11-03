"""Independent child-key-map replay with heights derived from structure, never runtime caches."""

from contract import (
    NodeColor,
    NodeState,
    OperationKind,
    OperationStatus,
    OperationStep,
    Rotation,
    RotationKind,
    TreeKind,
    TreeOutput,
    TreeSnapshot,
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def key_ok(key):
    require(type(key) is int and -(2**31) <= key <= 2**31 - 1, "key outside signed 32-bit range")


def inspect(root, links, tree_type=TreeKind.AVL, colors=None):
    colors = {key: None for key in links} if colors is None else colors
    require(set(colors) == set(links), "color table does not match node table")
    visited, rows, ordered = set(), [], []

    def scan(key, low=None, high=None):
        if key is None:
            return 0, 0
        key_ok(key)
        require(key in links and key not in visited, "unknown, cyclic, or shared node")
        require((low is None or key > low) and (high is None or key < high), "invalid BST ordering")
        visited.add(key)
        left, right = links[key]
        a, black_a = scan(left, low, key)
        ordered.append(key)
        b, black_b = scan(right, key, high)
        color = colors[key]
        if tree_type == TreeKind.AVL:
            require(abs(a - b) <= 1, "tree is not AVL-balanced")
        if tree_type == TreeKind.RED_BLACK:
            require(color in (NodeColor.RED, NodeColor.BLACK), "red-black color missing")
            require(colors.get(right) != NodeColor.RED, "red right link is not left-leaning")
            require(color != NodeColor.RED or colors.get(left) != NodeColor.RED, "consecutive red links")
            require(black_a == black_b, "unequal red-black path black heights")
        else:
            require(color is None, "color must be null for BST/AVL")
        rows.append(NodeState(key, left, right, 1 + max(a, b), a - b, color))
        return 1 + max(a, b), black_a + (color == NodeColor.BLACK)

    tree_height, _ = scan(root)
    require(tree_type != TreeKind.RED_BLACK or root is None or colors[root] == NodeColor.BLACK, "root is not black")
    require(visited == set(links), "disconnected node")
    return TreeSnapshot(root, sorted(rows, key=lambda row: row.key), ordered, tree_height, len(links))


def prepare(value):
    entries = [] if value.initial is None else value.initial.nodes
    root = None if value.initial is None else value.initial.root
    require(len(entries) <= 256 and len(value.operations) <= 128, "input exceeds node or operation limit")
    require(len({entry.key for entry in entries}) == len(entries), "duplicate node key")
    links = {entry.key: (entry.left, entry.right) for entry in entries}
    for key in links:
        key_ok(key)
    colors = {entry.key: entry.color for entry in entries}
    initial = inspect(root, links, value.tree_type, colors)
    keys, total = set(links), len(links)
    for operation in value.operations:
        key_ok(operation.key)
        if operation.kind == OperationKind.INSERT:
            keys.add(operation.key)
        else:
            keys.difference_update([operation.key])
        total += len(keys)
        require(len(keys) <= 256 and total <= 8192, "snapshot/node budget exceeded")
    return root, links, initial


def replay(value):
    from .red_black import update

    root, links, initial = prepare(value)
    colors = {entry.key: entry.color for entry in initial.nodes}
    steps, rotations = [], []

    def height(key):
        return 0 if key is None else 1 + max(height(links[key][0]), height(links[key][1]))

    def tilt(key):
        left, right = links[key]
        return height(left) - height(right)

    def right_turn(key):
        left, right = links[key]
        left_left, left_right = links[left]
        links[key] = (left_right, right)
        links[left] = (left_left, key)
        rotations.append(Rotation(RotationKind.RIGHT, key, left))
        return left

    def left_turn(key):
        left, right = links[key]
        right_left, right_right = links[right]
        links[key] = (left, right_left)
        links[right] = (key, right_right)
        rotations.append(Rotation(RotationKind.LEFT, key, right))
        return right

    def fix(key):
        if value.tree_type == TreeKind.BST:
            return key
        difference = tilt(key)
        if difference >= 2:
            left, right = links[key]
            if tilt(left) < 0:
                links[key] = (left_turn(left), right)
            return right_turn(key)
        if difference <= -2:
            left, right = links[key]
            if tilt(right) > 0:
                links[key] = (left, right_turn(right))
            return left_turn(key)
        return key

    def add(key, item):
        if key is None:
            links[item] = (None, None)
            return item
        if item == key:
            return key
        left, right = links[key]
        if item < key:
            links[key] = (add(left, item), right)
        else:
            links[key] = (left, add(right, item))
        return fix(key)

    def remove(key, item):
        if key is None:
            return None
        left, right = links[key]
        if item != key:
            if item < key:
                links[key] = (remove(left, item), right)
            else:
                links[key] = (left, remove(right, item))
            return fix(key)
        if left is None or right is None:
            del links[key]
            return right if left is None else left
        replacement = right
        while links[replacement][0] is not None:
            replacement = links[replacement][0]
        new_right = remove(right, replacement)
        del links[key]
        links[replacement] = (left, new_right)
        return fix(replacement)

    for operation in value.operations:
        existed = operation.key in links
        rotations, recolors = [], []
        if operation.kind == OperationKind.INSERT:
            if not existed:
                if value.tree_type == TreeKind.RED_BLACK:
                    root, rotations, recolors = update(root, links, colors, operation)
                else:
                    root = add(root, operation.key)
            status = OperationStatus.ALREADY_PRESENT if existed else OperationStatus.INSERTED
        else:
            if existed:
                if value.tree_type == TreeKind.RED_BLACK:
                    root, rotations, recolors = update(root, links, colors, operation)
                else:
                    root = remove(root, operation.key)
            status = OperationStatus.DELETED if existed else OperationStatus.NOT_FOUND
        if value.tree_type != TreeKind.RED_BLACK:
            colors = {key: None for key in links}
        steps.append(
            OperationStep(operation, status, list(rotations), inspect(root, links, value.tree_type, colors), recolors)
        )
    return TreeOutput(
        value, initial, steps, initial if not steps else steps[-1].tree, sum(len(step.rotations) for step in steps)
    )
