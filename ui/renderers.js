import { dataTable, disclosure, h, statusPill } from "./kit/components.js";

const diagram = (tree) => {
  if (tree.root === null) return h("p", { class: "empty-tree", text: "Empty tree ∅" });
  const nodes = new Map(tree.nodes.map((node) => [node.key, node]));
  const draw = (key) => {
    if (key === null) return h("span", { class: "null-node", text: "∅" });
    const node = nodes.get(key);
    const children = node.left !== null || node.right !== null;
    return h("div", { class: "tree-node" },
      h("span", { class: "node-key" + (node.color ? " color-" + node.color : ""), text: String(key) + (node.color ? (node.color === "red" ? " R" : " B") : ""), title: "Height " + node.height + ", balance " + node.balance + (node.color ? ", color " + node.color : "") }),
      children ? h("div", { class: "tree-children" },
        h("div", { class: "tree-branch" }, h("small", { text: "L" }), draw(node.left)),
        h("div", { class: "tree-branch" }, h("small", { text: "R" }), draw(node.right)),
      ) : null,
    );
  };
  return h("div", { class: "tree-scroll" }, draw(tree.root));
};

const treeNames = { bst: "Unbalanced BST", avl: "AVL", red_black: "Left-leaning red-black (2–3)" };
const policies = { bst: "BST preserves search order without balancing rotations.", avl: "AVL maintains a height difference of at most one at every node.", red_black: "LLRB keeps the root black, red links left-leaning, no consecutive reds, and equal black heights. R = red; B = black." };

const statuses = { inserted: "Inserted", deleted: "Deleted", already_present: "Already present; unchanged", not_found: "Not found; unchanged" };
const action = (operation) => (operation.kind === "insert" ? "Insert " : "Delete ") + operation.key;

export default {
  TreeOutput: (value, { verdict }) => {
    if (verdict?.valid === false) return h("section", { class: "avl" }, statusPill("Verification failed", "bad"), h("p", { text: verdict.message }));
    return h("section", { class: "avl" },
      statusPill(treeNames[value.request.tree_type] + " operations complete", "ok"),
      h("p", { text: policies[value.request.tree_type] }),
      h("p", { text: value.final.size + " keys; height " + value.final.height + "; " + value.total_rotations + " primitive rotations." }),
      diagram(value.final),
      h("p", { class: "inorder", text: "In-order: " + (value.final.inorder.length ? value.final.inorder.join(", ") : "∅") }),
      value.steps.length ? dataTable({ columns: [
        { key: "step", label: "Step", numeric: true }, { key: "operation", label: "Operation" },
        { key: "status", label: "Result" }, { key: "rotations", label: "Rotations", numeric: true },
      ], rows: value.steps.map((step, index) => ({ step: index + 1, operation: action(step.operation), status: statuses[step.status], rotations: step.rotations.length })), caption: "Operation sequence" }).element : h("p", { text: "No operations requested; inspecting the starting tree." }),
      disclosure({ summary: "Starting tree" }, diagram(value.initial)),
      value.steps.map((step, index) => disclosure({ summary: (index + 1) + ". " + action(step.operation) + " — " + statuses[step.status] },
        diagram(step.tree),
        h("p", { text: "Root: " + (step.tree.root ?? "∅") + "; size " + step.tree.size + "; height " + step.tree.height + "." }),
        step.rotations.length ? h("ol", {}, step.rotations.map((rotation) => h("li", { text: "Rotate " + rotation.kind + " at " + rotation.pivot + "; new subtree root " + rotation.new_root + "." }))) : h("p", { text: "No rotation needed." }),
        step.recolors.length ? h("ol", {}, step.recolors.map((change) => h("li", { text: "Recolor " + change.key + ": " + change.before + " → " + change.after + "." }))) : null,
      )),
      disclosure({ summary: "Final nodes, heights, balances and colors" }, dataTable({ columns: [
        { key: "key", label: "Key", numeric: true }, { key: "left", label: "Left child" },
        { key: "right", label: "Right child" }, { key: "height", label: "Height", numeric: true },
        { key: "balance", label: "Balance L − R", numeric: true }, { key: "color", label: "Color" },
      ], rows: value.final.nodes.map((node) => ({ ...node, left: node.left ?? "∅", right: node.right ?? "∅", color: node.color ?? "N/A" })), caption: "Verified final " + treeNames[value.request.tree_type] + " tree" }).element),
      h("p", { class: "muted", text: "Unique-key set semantics: duplicate keys are not inserted twice. Two-child deletion uses the in-order successor. Empty height is 0; leaf height is 1. The verifier checks every step, rotation, and recolor against the interpreted input and selected policy." }),
    );
  },
};
