# Tree Operations

**Insert, delete, and explore different balancing policies.** Describe ordered
operations in ordinary language and inspect the tree after every step, including
rotations, heights, balance factors, sorted traversal, and red-black colors.

Choose an **unbalanced binary search tree (BST)**, **AVL**, or **left-leaning
red-black tree (LLRB, the 2–3 variant)**. A separate verifier replays the selected
algorithm without importing its implementation. The local tool requires no API
key or model; RUSH chat uses its configured model to interpret the request.

## Tools

| Tool | Input → output | Purpose |
|---|---|---|
| `apply_operations` | `TreeInput` → `TreeOutput` | Apply ordered insert/delete operations using the chosen tree type, returning every snapshot, rotation, and recolor. |

| Task | Runner | Purpose |
|---|---|---|
| `tree-operations` | `tool`, calling `apply_operations` | Perform and independently verify the requested BST, AVL, or LLRB operations. |

### Try it in chat

```text
Start with an empty red-black tree. Insert 30, then 10, then 20.
Then delete 10. Show each tree, rotation, and color change.
```

The plugin uses the **left-leaning 2–3 variant** of red-black balancing and labels
it explicitly. Inserting 20 performs a left rotation at 10, a right rotation at
30, and color changes. Different red-black algorithms can produce different
valid shapes and traces; this plugin does not claim to implement every variant.

For a comparison:

```text
Run the same sequence separately on an empty BST, AVL tree, and red-black tree:
insert 30, then 20, then 10. Compare the final roots, heights, rotations, and colors.
```

The ordinary BST keeps root 30 and height 3, with no rotations. AVL and LLRB
finish with root 20 and height 2; AVL nodes are uncolored, while these LLRB nodes
are black. The host calls the tool once per type, preserving the same operation
sequence. AVL is the stated default when no type is requested for a new tree.

For an existing tree:

```text
Use a plain BST with root 30, left child 20, and 20's left child 10.
All other children are empty. Delete 20, then insert 25.
```

Existing red-black trees additionally require every node's red/black color.
Alternatively, supply an insertion sequence from an empty tree so the plugin
computes colors. For follow-ups, the chat preserves the previous tree type and
copies its final root and child links (and colors) into `initial`. The tool is
stateless; each call supplies its complete starting tree and operation sequence.
Users do not need to construct JSON.

### Exact rules

| `tree_type` | Policy | Required starting invariants |
|---|---|---|
| `bst` | Standard BST insertion/deletion, **no balancing rotations** | Global BST ordering; skewed shapes are allowed; colors null |
| `avl` | Rebalance on ascent with single/double rotations | Global BST ordering; every balance factor −1, 0, or 1; colors null |
| `red_black` | Left-leaning 2–3 red-black insertion/deletion | Global BST ordering; explicit colors; black root; no red right links; no consecutive red links; equal black heights |

- Keys are unique **signed 32-bit integers**, including zero and negatives.
  All left-subtree keys are smaller than their ancestor; all right-subtree keys
  are larger. Empty subtree height is **0**, leaf height **1**; balance is
  `height(left) - height(right)`. Only AVL restricts its absolute value to one.
- All types use the **in-order successor** (smallest right-subtree key) for a
  two-child deletion. Other valid conventions can yield different final shapes.
- AVL uses LL/RR single rotations and LR/RL double rotations. A heavy child with
  balance zero uses a single rotation. Deletion can rebalance several ancestors.
- LLRB insertion creates a red leaf, repairs right-red/consecutive-left-red
  links on ascent, and splits temporary 4-nodes by flipping colors. Deletion
  moves red links toward the removal path before descending, then restores the
  left-leaning form on ascent. The root is normalized to black after each change.
  Missing children are black; black height counts real black nodes, excluding NIL.
- A duplicate insertion reports `already_present`; an absent deletion reports
  `not_found`. Both leave the tree unchanged with **empty rotation and recolor
  traces**, including in red-black mode.
- **Operation order matters.** Never sort or deduplicate the sequence. An
  unordered set of keys does not identify a particular existing shape. Table
  row order for explicitly linked initial nodes does not matter.

Sources: [NIST's BST definition](https://xlinux.nist.gov/dads/HTML/binarySearchTree.html),
[NIST's AVL definition](https://xlinux.nist.gov/dads/HTML/avltree.html),
[Cornell's AVL deletion notes](https://courses.cs.cornell.edu/cs2112/2017fa/lectures/lec_avl/index.html),
and [Princeton's balanced search tree lectures](https://www.cs.princeton.edu/courses/archive/fall25/cos226/lectures/33BalancedSearchTrees.pdf)
describe the corresponding invariants. Exact operation conventions are stated
above so results remain reproducible.

### Input and output

`TreeInput` has three required fields:

- `tree_type`: `bst`, `avl`, or `red_black`. The chat explicitly supplies it;
  existing trees are never silently converted between policies.
- `initial`: null to start empty, or `{root, nodes}`. Every initial node has
  `{key, left, right, color}`; children are keys or null. Color is null for
  BST/AVL and `red`/`black` for LLRB. Heights/balances are computed, not inputs.
- `operations`: ordered `{kind, key}` entries, with `insert` or `delete`.
  Leading inserts build a tree from a specified sequence. An empty list inspects
  the starting tree without changing it.

`TreeOutput` echoes `request` and supplies `initial`, `steps`, `final`, and
`total_rotations`. Each step has its `operation`, `status`, `rotations`, `recolors`,
and `tree`. Snapshots contain `root`, `nodes` sorted by key, `inorder`, `height`,
and `size`; node rows include links, height, balance, and color.

Each primitive rotation records direction, pivot, and new root. A double
rotation has two entries. Each recolor records a key and its before/after color;
only actual changes count, including temporary root changes. Creating a new red
leaf is not a recolor. Rotation and recolor lists each preserve their own
execution order; they are separate traces, not one interleaved event list. A key
in a recolor refers to the node at that moment, before a subsequent deletion or
successor-key replacement. Deleted nodes can therefore appear in a color trace.

The UI labels the selected policy, draws the initial and intermediate trees,
shows L/R edges, labels red-black nodes with R/B as well as color, lists rotations
and recolors, and exposes final node metadata.

### Verification and limits

The runtime uses mutable node objects and cached heights. The independent
verifier uses child-key/color dictionaries, recomputes heights from structure,
and imports only the contract and its own pure helpers. It checks one connected,
acyclic tree, global BST bounds, exact contents, heights, colors, and the selected
policy's invariants after every operation. It also replays the declared algorithm
and compares **every output field**, including operation order, no-op statuses,
all snapshots, rotations, and recolors. A legitimate result from a different
balancing variant still fails this task's exact declared convention.

The verifier uses no model, network, randomness, clock, or workspace IO. Correct
empty/no-op results score 1. Wrong or missing results score 0; malformed typed
payloads are rejected. Invalid starting shapes, cycles, shared/missing child
nodes, disconnected nodes, and incorrect colors are explicit input errors.

Limits remain **256 live nodes**, **128 operations**, and **8,192 node entries
across initial and per-operation snapshots**, combined. A large-tree history can
hit the snapshot bound first. Input is fully validated before performing updates;
there is no silently truncated result. These bounded educational traces are not
a production collection or a performance benchmark.

This plugin supports three integer-key **search tree** policies, not B-trees,
splay trees, heaps, multisets, arbitrary object keys, delayed bulk balancing, or
repair/conversion of invalid starting trees. Conventional red-black trees that
have right-leaning red links are outside the LLRB input contract even when they
satisfy general red-black invariants.

Verification is conditional on the **interpreted tree type, starting shape,
colors, and operation sequence**. The host can mistranslate prose or reuse the
wrong prior state; a deterministic checker cannot certify arbitrary English
interpretation. The echoed input, diagrams, and traces make the actual
interpretation reviewable. Local validation does not establish hosted chat or
real-browser rendering behavior.

## Layout

```text
avl-tree-operations/
├── nanoagent.yaml          # Tree Operations, stable original plugin ID
├── contract.py
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env                   # comments only
├── src/plugin/            # MCP, pointer-based BST/AVL and LLRB updates
├── verifier/              # separate key-map replay and structural/color audit
├── tests/
│   ├── cases/             # hand-specified shapes, rotations and recolors
│   └── test_verifier.py
├── ui/                    # diagrams, trace disclosures and node tables
└── product/
```

This is one independently usable Git repository and uv project. It imports
nothing from other plugins or the milestone parent. The existing folder,
package name, and plugin ID `avl-tree-operations` are retained for continuity;
the displayed name is now **Tree Operations**, version **0.2.0**. The expanded
contract requires explicit type and color fields, so old v0.1.0 JSON payloads
must add `tree_type: avl`, null colors, and empty recolor lists in expected steps.

## Develop and run

```bash
uv sync --frozen --extra dev
uv run --frozen --extra dev pytest
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
```

Install the separately pinned NanoAgent CLI if needed:

```bash
uv tool install 'nanoagent @ git+https://github.com/RUSH-LAB/nanoagent.git@57714f62880eee11319765854e398af61e67b7b7#subdirectory=nanoagent'
nanoagent plugin inspect .
```

Save a YAML config **outside the repository**, replacing absolute paths:

```yaml
_ > nanoagent.cli.plugin.PluginRunConfig:
plugin: /absolute/path/to/avl-tree-operations
task: tree-operations
arguments: /absolute/path/to/avl-tree-operations/tests/cases/rb-delete-black-leaf.input.json
inputs: []
timeout: 60.0
```

Run and package:

```bash
nanoagent plugin run config=/absolute/path/to/run.yaml home=/absolute/path/to/evidence/run
nanoagent plugin pack . /absolute/path/to/evidence/avl-tree-operations.tar.gz
```

Local tasks require no model/API key. This repository is initialized on `main`;
no remote, push, marketplace publication, or paid chat test is implied by a local
build. After pushing changes to its own GitHub repository, publish the new
version through the RUSH marketplace to update the published plugin.
