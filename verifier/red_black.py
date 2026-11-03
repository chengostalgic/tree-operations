"""Pure LLRB oracle over child-key/color maps, with no runtime imports or caches."""

from contract import NodeColor, OperationKind, Recolor, Rotation, RotationKind


def update(root, edges, colors, operation):
    rotations, recolors = [], []

    def is_red(key):
        return key is not None and colors[key] == NodeColor.RED

    def color(key, after):
        before = colors[key]
        if before != after:
            recolors.append(Recolor(key, before, after))
            colors[key] = after

    def turn(key, leftward):
        a, b = edges[key]
        next_root = b if leftward else a
        c, d = edges[next_root]
        edges[key] = (a, c) if leftward else (d, b)
        edges[next_root] = (key, d) if leftward else (c, key)
        rotations.append(Rotation(RotationKind.LEFT if leftward else RotationKind.RIGHT, key, next_root))
        color(next_root, colors[key])
        color(key, NodeColor.RED)
        return next_root

    def invert(key):
        for item in (key, *edges[key]):
            color(item, NodeColor.BLACK if is_red(item) else NodeColor.RED)

    def restore(key, insertion=False):
        a, b = edges[key]
        if is_red(b) and (not insertion or not is_red(a)):
            key = turn(key, True)
        a, b = edges[key]
        if is_red(a) and is_red(edges[a][0]):
            key = turn(key, False)
        a, b = edges[key]
        if is_red(a) and is_red(b):
            invert(key)
        return key

    def promote(key, toward_left):
        invert(key)
        a, b = edges[key]
        if toward_left and is_red(edges[b][0]):
            edges[key] = (a, turn(b, False))
            key = turn(key, True)
            invert(key)
        elif not toward_left and is_red(edges[a][0]):
            key = turn(key, False)
            invert(key)
        return key

    def attach(key, item):
        if key is None:
            edges[item], colors[item] = (None, None), NodeColor.RED
            return item
        a, b = edges[key]
        edges[key] = (attach(a, item), b) if item < key else (a, attach(b, item))
        return restore(key, insertion=True)

    def erase_min(key):
        a, b = edges[key]
        if a is None:
            del edges[key], colors[key]
            return None
        if not is_red(a) and not is_red(edges[a][0]):
            key = promote(key, True)
        a, b = edges[key]
        edges[key] = (erase_min(a), b)
        return restore(key)

    def erase(key, item):
        a, b = edges[key]
        if item < key:
            if not is_red(a) and not is_red(edges[a][0]):
                key = promote(key, True)
            a, b = edges[key]
            edges[key] = (erase(a, item), b)
        else:
            if is_red(a):
                key = turn(key, False)
            a, b = edges[key]
            if item == key and b is None:
                del edges[key], colors[key]
                return None
            if not is_red(b) and not is_red(edges[b][0]):
                key = promote(key, False)
            a, b = edges[key]
            if item == key:
                replacement = b
                while edges[replacement][0] is not None:
                    replacement = edges[replacement][0]
                new_b = erase_min(b)
                old_color = colors[key]
                del edges[key], colors[key]
                edges[replacement], colors[replacement] = (a, new_b), old_color
                key = replacement
            else:
                edges[key] = (a, erase(b, item))
        return restore(key)

    if operation.kind == OperationKind.INSERT:
        root = attach(root, operation.key)
    else:
        a, b = edges[root]
        if not is_red(a) and not is_red(b):
            color(root, NodeColor.RED)
        root = erase(root, operation.key)
    if root is not None:
        color(root, NodeColor.BLACK)
    return root, rotations, recolors
