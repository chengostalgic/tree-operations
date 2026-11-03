"""Pure independent input audit and full operation/rotation replay."""

from .avl import prepare, replay


def verdict(valid, message, **details):
    return {"valid": valid, "score": 1.0 if valid else 0.0, "message": message, "details": details}


def verify_input(tool, value):
    if tool != "apply_operations":
        return verdict(False, "unknown tool")
    try:
        prepare(value)
    except ValueError as error:
        return verdict(False, str(error))
    return verdict(True, "valid starting tree of the selected type and bounded operation sequence")


def check_result(given, made):
    if made is None:
        return verdict(False, "missing tree result")
    try:
        expected = replay(given)
    except ValueError as error:
        return verdict(False, "invalid input: " + str(error))
    if made != expected:
        return verdict(
            False,
            "tree, type, color, operation status, height, balance, or balancing trace differs from independent replay",
        )
    return verdict(
        True,
        "every operation, rotation, recolor, and typed tree snapshot is correct",
        tree_type=given.tree_type.value,
        final_size=expected.final.size,
        final_height=expected.final.height,
        rotations=expected.total_rotations,
    )


def verify_output(tool, input_value, output_value, workspace):
    return check_result(input_value, output_value) if tool == "apply_operations" else verdict(False, "unknown tool")


def verify_task(task, arguments, output, reference, workspace):
    return check_result(arguments, output) if task == "tree-operations" else verdict(False, "unknown task")
