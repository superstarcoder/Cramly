# Binary Search Trees (BST) — Cheat Sheet

## TL;DR
- **BST Properties**: Left < Root < Right
- **Operations**: Insert, Delete, Search in $O(\log n)$ time *average*
- **Traversal Orders**: Inorder → <span class="tip">Sorted output</span>
- <span class="warn">Imbalance</span> can degrade to $O(n)$
- **Balanced BSTs**: AVL, Red-Black Trees maintain $O(\log n)$

## Key Terms

| Term | Definition |
| --- | --- |
| <span class="key">Binary Search Tree (BST)</span> | A tree with nodes in left < root < right order |
| <span class="key">Root Node</span> | Topmost node in the tree |
| <span class="key">Leaf Node</span> | Node with no children |
| <span class="key">Height</span> | Longest path from root to a leaf |
| <span class="key">AVL Tree</span> | A self-balancing binary search tree |
| <span class="key">Red-Black Tree</span> | A balanced BST using color properties |

## Core Concepts

### BST Properties
- **Structure**: Binary tree where each node has max two children.
- **Rule**: Left descendants ≤ node ≤ right descendants.
- **Paths**: All paths from root to leaf involve searching left or right.

### Traversal Orders
- **In-order**: Left → Root → Right — Produces sorted sequence.
- **Pre-order**: Root → Left → Right.
- **Post-order**: Left → Right → Root.
- **Level-order**: Breadth-first search.

### Operations
- **Search**: Compare against root, recur left/right (worst $O(n)$).
- **Insertion**: Find empty spot following BST rule, insert there.
- **Deletion**: 
  - **No child**: Remove leaf.
  - **One child**: Bypass the node.
  - **Two children**: Find in-order successor/predecessor.

## Formulas / Rules

| Formula / Rule | Symbols | When to Apply |
| --- | --- | --- |
| Height (\(h\)) | $h = \log_2(n)$ | Balanced BST |
| Number of Nodes | $n = 2^{h+1} - 1$ | Full BST |
| Balanced Condition (AVL) | $|height(left) - height(right)| \leq 1$ | Post-insertion |

## Worked Mini-Examples

1. **Inserting 5 into BST [2,3,4,7]:**
   - Steps: 7 > 5, place 5 as left child of 7
   - Result: [2,3,4,5,7]

2. **Deleting node 4 with two children [2,3,4,7]:**
   - Find in-order successor (5)
   - Replace 4 with 5
   - Result: [2,3,5,7]

## Common Mistakes / Gotchas
- <span class="warn">Misplacing Nodes</span>: Always verify position during insertions.
- **Assumption**: Thinking average $O(\log n)$ is guaranteed without balance.
- **Skipping Traversals**: Missing inverted order (sorted descending).
- <span class="warn">Forgetting Edge Cases</span>: Handle leaf and no-child nodes correctly in deletions.

## Quick-Check Questions
1. What is a BST?
2. Describe in-order traversal.
3. How do you find a node's successor?
4. What guarantees $O(\log n)$ operations in BSTs?
5. How would you delete a node with two children?
6. What's the worst-case complexity of searching in a degenerate BST?
7. What tree property guarantees sorted in-order output?
8. How do you maintain balance in an AVL tree?

## Answers
1. A tree where left subtree < root < right subtree.
2. Left → Root → Right, producing sorted order.
3. Successor is the leftmost node of the right subtree.
4. The tree is balanced (e.g., AVL, Red-Black).
5. Replace with in-order successor or predecessor.
6. $O(n)$
7. In-order traversal.
8. By rotating nodes and maintaining height condition.