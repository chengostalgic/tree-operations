"""Left-leaning 2-3 red-black updates on mutable nodes with cached heights.

Insertion repairs on ascent; deletion moves a red link toward the removal path
before descending, then restores left-leaning form on ascent. NIL is black.
"""

from contract import NodeColor, OperationKind, Recolor, RotationKind

from .avl import Node, refresh, rotate


def red(node):
    return node is not None and node.color == NodeColor.RED


def update(root, operation, rotations, recolors):
    def paint(node, color):
        if node.color != color:
            recolors.append(Recolor(node.key, node.color, color))
            node.color = color

    def turn(node, direction):
        color = node.color
        parent = rotate(node, direction, rotations)
        paint(parent, color)
        paint(node, NodeColor.RED)
        return parent

    def flip(node):
        for current in (node, node.left, node.right):
            paint(current, NodeColor.BLACK if red(current) else NodeColor.RED)

    def fix(node, inserting=False):
        if red(node.right) and (not inserting or not red(node.left)):
            node = turn(node, RotationKind.LEFT)
        if red(node.left) and red(node.left.left):
            node = turn(node, RotationKind.RIGHT)
        if red(node.left) and red(node.right):
            flip(node)
        return refresh(node)

    def add(node, key):
        if node is None:
            return Node(key, color=NodeColor.RED)
        if key < node.key:
            node.left = add(node.left, key)
        else:
            node.right = add(node.right, key)
        return fix(node, inserting=True)

    def move_red_left(node):
        flip(node)
        if red(node.right.left):
            node.right = turn(node.right, RotationKind.RIGHT)
            node = turn(node, RotationKind.LEFT)
            flip(node)
        return node

    def move_red_right(node):
        flip(node)
        if red(node.left.left):
            node = turn(node, RotationKind.RIGHT)
            flip(node)
        return node

    def pop_min(node):
        if node.left is None:
            return None
        if not red(node.left) and not red(node.left.left):
            node = move_red_left(node)
        node.left = pop_min(node.left)
        return fix(node)

    def remove(node, key):
        if key < node.key:
            if not red(node.left) and not red(node.left.left):
                node = move_red_left(node)
            node.left = remove(node.left, key)
        else:
            if red(node.left):
                node = turn(node, RotationKind.RIGHT)
            if key == node.key and node.right is None:
                return None
            if not red(node.right) and not red(node.right.left):
                node = move_red_right(node)
            if key == node.key:
                successor = node.right
                while successor.left is not None:
                    successor = successor.left
                node.key = successor.key
                node.right = pop_min(node.right)
            else:
                node.right = remove(node.right, key)
        return fix(node)

    if operation.kind == OperationKind.INSERT:
        root = add(root, operation.key)
    else:
        if not red(root.left) and not red(root.right):
            paint(root, NodeColor.RED)
        root = remove(root, operation.key)
    if root is not None:
        paint(root, NodeColor.BLACK)
    return root
