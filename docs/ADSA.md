# KAIROS v1.0 — Internal ADSA and viva notes

This document contains technical and historical material from earlier project reviews. It is not
the current product specification. Use the repository root [README](../README.md) for the current
product workflow, setup, API, privacy, limitations, and end-to-end demo.

## Current product description

KAIROS is an adaptive academic productivity and knowledge-management system that helps users
organize work, discover resources from folders they choose, plan around deadlines and available
time, choose a recommended next action, focus, track progress, and adapt remaining work.

The primary product UI is subject-independent. It does not expose algorithm names, an Algorithm
Lab, structure inspection, or strategy comparisons. The backend retains meaningful structures,
algorithms, and measurement endpoints for technical evaluation.

## Product evolution

After the mid-semester review, the initial Smart Task Scheduler concept was refined into KAIROS,
an adaptive academic productivity and knowledge-management system. The project evolved from simple
task scheduling into task management, local resource discovery, adaptive planning, progress
tracking, and deadline-risk awareness.

## Profiling-driven structure changes (25 October 2026)

Two indexing paths were quadratic in the number of library files. Both were found by measurement
(`backend/scripts/profile_kairos.py`) and both fixes reuse the hand-written hash table:

- **Duplicate check while indexing.** For every file walked, indexing asked "is this path already
  in the library?" by scanning every stored resource: O(n) per file, O(n·m) per folder. A second
  `HashTable` (location → resource id), kept in step with the resource table, makes the check
  O(1) on average.
- **Trie payload de-duplication.** A Trie word node stored its resource ids in a list and checked
  `payload not in list` before appending: O(k) per insert. Words that most files share (file kind,
  extension, tags) have k close to n, so indexing n files was O(n²) for those words. A node now
  builds a `HashTable` membership index once it holds more than 16 payloads (O(1) average check);
  small nodes keep the plain list. Insertion order, and therefore search order, is unchanged.

On the profile machine, indexing a second 1,500-file folder into a 1,500-file library went from
about 3 s to about 1.2 s, roughly the cost of indexing into an empty library. That is the
expected result once each file costs O(1) average work. AUDIT.md has the full table and the
measurement environment.

## Implementation map (technical notes, 25 October 2026)

These notes are for maintainers and viva preparation. The product interface, README, and final-review material
describe capabilities, not these internals.

| Implementation | Product role | Complexity |
|---|---|---|
| AVL tree | tasks ordered by deadline; insert/delete | O(log n) update, O(n) traversal |
| Binary max-heap | task priority view; candidates for the recommended next action | O(log n) insert/extract, O(1) peek |
| Hash table | task/resource lookup; file-location index for duplicate checks while indexing; library folders | O(1) average lookup, O(n) worst case |
| Trie | resource keyword and prefix lookup; words shared by many files keep a hash-table payload index | O(m + k) prefix traversal/output; O(1) average duplicate-payload check |
| Heap + heapsort | top-k search results and display order; ordering tasks for the weekly plan | O(n + k log n) ranking pipeline |
| Greedy / dynamic programming / backtracking / branch and bound | capacity-limited task selection behind the `/api/schedule` compatibility endpoint only | O(n log n) greedy; O(nW) DP; O(2^n) worst case for exact search |

The weekly plan shown in the interface (`/api/plan`) does not use the four selection strategies: it orders open
tasks by deadline, then urgency, and fills each day up to the daily hours and the weekly total, reporting any
remainder as not yet scheduled. The benchmarking, structure-inspection, and strategy-comparison endpoints were
removed on 25 October 2026; the strategies' correctness is still covered by `tests/test_scheduler.py`.

## Historical review material

The sections below preserve earlier ADSA planning and presentation notes. Their proposed product
screens and claims describe historical scope; do not treat them as evidence of current v1.0
behavior. Current implementation evidence and known gaps are tracked in [AUDIT.md](../AUDIT.md).

---
2. Objectives

### Core objectives

1. Manage assignments, projects, deadlines, and academic tasks.
2. Analyze the topic and estimated workload of each task.
3. Index and search relevant **local study resources**.
4. Retrieve useful **web-based educational resources**.
5. Use **Trie** for fast prefix and keyword searching.
6. Use **Hash Tables** for efficient resource and task lookup.
7. Use **AVL Trees** for deadline-based task organization.
8. Use **Binary Heaps** for task prioritization and Top-K resource retrieval.
9. Apply **Heapsort** for efficient ranking and sorting.
10. Apply **Greedy algorithms** for fast scheduling.
11. Apply **Dynamic Programming** for optimized scheduling.
12. Use **Backtracking and Branch & Bound** for alternative/constrained schedules.
13. Adapt learning plans based on student progress.
14. Generate intelligent reminders based on workload and deadline.
15. Automatically organize resources into task-specific workspaces.
16. Experimentally compare algorithms based on **time and space complexity**.

---

# 3. Architecture

```text

\&#x20;                        ┌──────────────────────┐

\&#x20;                        │      USER UI         │

\&#x20;                        │ Tasks | Learning     │

\&#x20;                        │ Calendar | Resources │

\&#x20;                        │ Analytics            │

\&#x20;                        └──────────┬───────────┘

\&#x20;                                   ↓

\&#x20;                        ┌──────────────────────┐

\&#x20;                        │    TASK ANALYZER     │

\&#x20;                        │ Topic | Deadline     │

\&#x20;                        │ Priority | Workload  │

\&#x20;                        └──────────┬───────────┘

\&#x20;                                   ↓

\&#x20;             ┌─────────────────────┼─────────────────────┐

\&#x20;             ↓                     ↓                     ↓

\&#x20;       ┌───────────┐         ┌───────────┐        ┌───────────┐

\&#x20;       │ AVL TREE  │         │ MAX HEAP  │        │ HASH TABLE│

\&#x20;       │ Deadlines │         │ Priority  │        │ Lookup    │

\&#x20;       └─────┬─────┘         └─────┬─────┘        └─────┬─────┘

\&#x20;             └─────────────────────┼─────────────────────┘

\&#x20;                                   ↓

\&#x20;                        ┌──────────────────────┐

\&#x20;                        │ RESOURCE ENGINE      │

\&#x20;                        └──────────┬───────────┘

\&#x20;                                   ↓

\&#x20;                   ┌───────────────┴───────────────┐

\&#x20;                   ↓                               ↓

\&#x20;            ┌──────────────┐               ┌──────────────┐

\&#x20;            │ LOCAL FILES  │               │ WEB RESOURCES│

\&#x20;            │ Trie + Hash  │               │ Search/API   │

\&#x20;            └──────┬───────┘               └──────┬───────┘

\&#x20;                   └──────────────┬────────────────┘

\&#x20;                                  ↓

\&#x20;                        ┌─────────────────────┐

\&#x20;                        │ RESOURCE RANKER     │

\&#x20;                        │ Heap + Scoring      │

\&#x20;                        └──────────┬──────────┘

\&#x20;                                   ↓

\&#x20;                        ┌─────────────────────┐

\&#x20;                        │ ADAPTIVE LEARNING   │

\&#x20;                        │ Progress | Weakness │

\&#x20;                        └──────────┬──────────┘

\&#x20;                                   ↓

\&#x20;                        ┌─────────────────────┐

\&#x20;                        │ SCHEDULING ENGINE   │

\&#x20;                        │ Greedy | DP | B\\\&B   │

\&#x20;                        │ Backtracking        │

\&#x20;                        └──────────┬──────────┘

\&#x20;                                   ↓

\&#x20;             ┌─────────────────────┼─────────────────────┐

\&#x20;             ↓                     ↓                     ↓

\&#x20;       ┌─────────────┐      ┌─────────────┐      ┌──────────────┐

\&#x20;       │ WORKSPACE   │      │ REMINDERS   │      │ ALGORITHM LAB│

\&#x20;       │ Resources   │      │ Adaptive    │      │ Benchmarking │

\&#x20;       └─────────────┘      └─────────────┘      └──────────────┘

```

### The important part

The **Algorithm Lab is not just a dashboard**.

It should actually execute your implementations against controlled datasets and collect measurements.

---

# 4. Methodology

## Phase 1 — Task creation

Student enters:

> \\\*\\\*ADSA Lab — AVL Tree\\\*\\\*  
> Deadline: Friday 5 PM  
> Estimated effort: 5 hours

---

## Phase 2 — Task analysis

The system identifies:

- Topic
- Deadline
- Priority
- Workload
- Required concepts
- Available preparation time

---

## Phase 3 — Resource indexing

Selected local directories are indexed.

Example:

```text

ADSA/

├── Unit\\\_1.pdf

├── Unit\\\_2.pdf

├── AVL\\\_Notes.pdf

├── Lab\\\_Manual.pdf

└── Previous\\\_Lab.pdf

```

The system builds:

**Trie →** keyword/prefix search

**Hash Table →** keyword → file mapping

---

## Phase 4 — Web resource discovery

The system searches for relevant educational resources and stores metadata such as:

- Title
- Source
- URL
- Topic
- Relevance
- Resource type

It should **retain source attribution and links**, rather than presenting web material as if it were locally generated.

---

## Phase 5 — Resource ranking

The system calculates relevance scores and uses a **Heap** to retrieve the Top-K resources.

Example:

```text

★★★★★ AVL Tree Lecture Notes

★★★★★ AVL Visualization

★★★★☆ AVL Practice Problems

★★★☆☆ Binary Tree Tutorial

```

---

## Phase 6 — Workspace creation

```text

ADSA - AVL Tree

│

├── Local Resources

├── Web Resources

├── Assignment

├── Practice

├── Progress

└── Study Plan

```

---

## Phase 7 — Adaptive learning

The topic is broken into concepts:

```text

BST

\&#x20;↓

Balance Factor

\&#x20;↓

Rotations

\&#x20;↓

Insertion

\&#x20;↓

Deletion

```

After practice:

```text

BST             90%

Balance Factor  85%

Rotations       52%

Insertion       81%

```

The system identifies **Rotations** as a weak area and allocates additional learning time.

---

# 5. Algorithm Lab / Analytics ⭐

This is the improvement I would **definitely keep**.

Instead of hardcoding example numbers like:

```text

Greedy = 1.2 ms

DP = 18.7 ms

```

your application should **measure them experimentally**.

### Scheduling Benchmark

For example:

```text

SCHEDULING PERFORMANCE



Input Tasks: 1,000



Algorithm             Execution Time

─────────────────────────────────────

Greedy                1.21 ms

Dynamic Programming  18.64 ms

Backtracking         243.10 ms

Branch \\\& Bound        96.42 ms

```

The actual values will depend on your implementation and machine.

### Search Benchmark

```text

SEARCH PERFORMANCE



Resources: 100,000



Algorithm             Execution Time

─────────────────────────────────────

Linear Search          8.42 ms

BST                    1.34 ms

AVL                    1.12 ms

Hash Table             0.18 ms

Trie                   0.21 ms

```

Again, **these are example values, not guaranteed results**.

### Even better

Allow the user to select:

```text

Dataset Size:

\\\[100] \\\[1,000] \\\[10,000] \\\[100,000]



Algorithm:

☑ Linear Search

☑ BST

☑ AVL

☑ Hash Table

☑ Trie



\\\[ RUN BENCHMARK ]

```

Then generate:

- Execution-time graph
- Memory usage
- Number of operations
- Complexity
- Speed comparison

This makes the project **experimentally defensible**.

---

# 6. Novelty

This needs to be stated carefully.

### ❌ Don't claim:

> "No existing application provides adaptive academic planning."

That's demonstrably too broad. Current products already offer combinations of personalized planning, deadlines, progress tracking, quizzes, and adaptive learning.

### ✅ Your actual differentiation:

### **1. Algorithm-first architecture**

Most existing study planners focus on the **user experience and AI-generated planning**.

AlgoSync makes the **data structures and algorithms themselves a core computational component**.

---

### **2. Local resource intelligence**

The system doesn't only ask:

> "What should I study?"

It asks:

> \\\*\\\*"What resources already exist on my computer that can help me complete this specific task?"\\\*\\\*

That creates a direct connection between **deadline and personal knowledge repository**.

---

### **3. Algorithmic resource retrieval**

Instead of generic search:

```text

Topic

\&#x20;↓

Trie

\&#x20;↓

Hash Index

\&#x20;↓

Relevance Scoring

\&#x20;↓

Heap

\&#x20;↓

Top-K Resources

```

---

### **4. Adaptive scheduling + learning**

The system doesn't simply create a static timetable.

If the student struggles:

```text

Weak topic detected

\&#x20;      ↓

Additional learning time

\&#x20;      ↓

Schedule changes

\&#x20;      ↓

Reminder changes

```

---

### **5. Built-in Algorithm Laboratory**

This is probably your **strongest academic differentiator**.

Instead of saying:

> "Hash Table is faster."

AlgoSync can demonstrate:

> \\\*\\\*"Here is the measured performance of Hash Table vs AVL vs Trie for our dataset."\\\*\\\*

That directly connects theory to implementation.

---

# 7. Does this idea already exist?

### **Yes — partially.**

There are several categories of similar products.

| Existing category | Examples | What they already do |
|---|---|---|
| AI study planners | Ahead, RealStudy | Deadlines → study schedules |
| AI study assistants | Ryko, StudyLumo | Planning + tutoring + quizzes |
| Adaptive learning | DK-PRACTICE | Knowledge assessment → personalized resources |
| Student productivity apps | NowOne | Tasks + calendar + files + progress |
| AI assignment planners | Emerging tools | Assignment → generated work plan |

Ahead, for example, turns a syllabus into a personalized semester plan and breaks it into weekly activities.  RealStudy similarly creates study blocks from assignments, priorities, deadlines, and available hours.

Adaptive-learning research platforms such as **DK-PRACTICE** focus on assessing knowledge gaps and recommending learning material based on the student's knowledge state.

So the **overall problem is not new**.

### But your project differs in this combination:

```text

Existing Study Planner

\&#x20;       ↓

Deadline → Study Plan





AlgoSync

\&#x20;       ↓

Deadline

\&#x20;  ↓

Topic Analysis

\&#x20;  ↓

Local Resource Index

\&#x20;  ↓

Web Resource Discovery

\&#x20;  ↓

Trie / Hash / Heap

\&#x20;  ↓

Resource Ranking

\&#x20;  ↓

Adaptive Learning

\&#x20;  ↓

AVL + Heap

\&#x20;  ↓

Greedy / DP / B\\\&B

\&#x20;  ↓

Optimized Schedule

\&#x20;  ↓

Adaptive Reminder

\&#x20;  ↓

Algorithm Benchmark

```

That's the distinction I would present to your professor.

---

# 8. Real-World Example

### Scenario

You receive:

> \\\*\\\*ADSA Lab Assignment\\\*\\\*  
> Topic: AVL Tree  
> Deadline: Friday, 5 PM.

You create it Monday morning.

### AlgoSync:

**1. Finds your local resources**

```text

AVL\\\_Notes.pdf

Unit\\\_2.pdf

Lab\\\_Manual.pdf

Previous\\\_AVL\\\_Lab.pdf

```

**2. Finds external resources**

```text

AVL visualization

AVL tutorial

AVL practice questions

```

**3. Creates**

```text

📁 ADSA - AVL Tree Lab

```

**4. Builds learning plan**

```text

Monday     → BST revision

Tuesday    → Balance Factor + Rotations

Wednesday  → Insertion

Thursday   → Deletion + Practice

Friday     → Final Review

```

**5. Measures your progress**

You score poorly on rotations.

```text

Rotations → 48%

```

The system adapts:

```text

Thursday

45 min → Rotation revision

30 min → Rotation problems

45 min → Assignment

```

**6. Scheduling engine**

If multiple assignments exist, it compares scheduling strategies and selects an appropriate schedule.

**7. Reminder**

Instead of a generic:

> "Assignment due tomorrow."

you receive:

> \\\*\\\*"AVL assignment is due tomorrow at 5 PM. Approximately 2.5 hours of work remain. Your scheduled rotation practice begins now."\\\*\\\*

**8. Algorithm Lab**

Afterward, you can demonstrate how your Trie, Hash Table, AVL Tree, Heap, and scheduling algorithms performed.

---

# 9. Time Required

For a **3–4 member team**:

| Component | Time |
|---|---:|
| Requirements + architecture | 2–3 days |
| Trie + Hash Table | 3–4 days |
| AVL + Heap | 4–5 days |
| Task management | 2–3 days |
| Local file indexing | 3–5 days |
| Web resource module | 3–5 days |
| Scheduling algorithms | 5–7 days |
| Adaptive learning | 4–6 days |
| Workspace/reminders | 2–4 days |
| Algorithm Lab | 3–5 days |
| UI integration | 4–6 days |
| Testing + benchmarking | 3–5 days |
| Documentation/presentation | 2–3 days |

### **Full version: ~5–7 weeks**

### MVP: ~2–3 weeks

I'd strongly recommend building the MVP first and then adding the web/adaptive-learning components.

---

# 10. Final Rating

After adding the **Algorithm Lab / Analytics**, my rating changes slightly:

| Criterion | Score |
|---|---:|
| ADSA syllabus alignment | **9.8/10** |
| Technical depth | **9.7/10** |
| Practical usefulness | **9.5/10** |
| Demo potential | **9.8/10** |
| Innovation/differentiation | **9.0/10** |
| Real-world relevance | **9.5/10** |
| Feasibility | **8.0/10** |
| Viva potential | **9.9/10** |
| Research/experimental value | **9.5/10** |

# 🏆 **Overall: 9.4/10**

--------------------------------------------------------------------------------------------------------------------------------------

MID Review :

# AlgoSync — Semester Project Split & Build Prompt

## 1. How to split the project

This is a DSA course project, so the mid-review priority is different from a typical app demo:
the professor needs to see your **core data structures actually working and driving real
behavior** — not just a nice UI. Save the algorithmic "intelligence" (scheduling optimization,
adaptive learning) for final review, since those build on top of a working data layer.

### MID REVIEW — "Core Data Engine"
Goal: prove the foundational structures are implemented correctly (ideally from scratch, not
just `dict`/`heapq` calls) and wired into a real task/resource workflow end-to-end.

**In scope for mid:**
- Task Analyzer (basic) — takes topic, deadline, priority, rough workload estimate on task
  creation (simple rule-based estimate is fine, no ML needed yet)
- **AVL Tree** — stores tasks keyed by deadline, keeps them balanced, supports in-order
  traversal for "upcoming tasks" view
- **Hash Table** (built yourself, with your own collision handling) — O(1) task/resource
  lookup by ID/keyword
- **Trie** — prefix/keyword search + autocomplete over indexed local resource filenames/tags
- **Binary Heap** (Max-Heap) — task prioritization queue and Top-K resource retrieval
- **Heapsort** — used to rank resources before displaying them
- Resource Engine — index a selected local folder (filename, tags, simple text extraction),
  plus one simple web resource fetch (e.g. a search API call) merged into the same ranking
- Workspace assembly — task-specific view showing its ranked resources
- Frontend (shadcn/ui): task creation form, task list sorted via AVL in-order traversal,
  resource search bar backed by the Trie, ranked resource panel, a small "algorithm trace"
  panel showing which structure/operation just ran (great for demoing DSA visibly)
- Backend: runnable API exposing task CRUD, resource search, and ranking — each endpoint
  should visibly use the corresponding structure (not swapped for a shortcut)

**Explicitly out of scope for mid** (defer to final):
- Greedy / Dynamic Programming / Backtracking / Branch & Bound scheduling
- Adaptive Learning Engine (progress tracking, weakness detection, plan adjustment)
- Reminders engine
- Algorithm Lab / Analytics (benchmarking, complexity comparison charts)

### FINAL REVIEW — "Adaptive Scheduling & Analytics"
Adds on top of the mid-review base:
- Scheduling Engine — implement and compare Greedy, DP, Backtracking, and Branch & Bound
  approaches to building a study schedule from prioritized tasks
- Adaptive Learning Engine — adjusts the plan based on tracked progress and identified weak
  topics
- Reminder generation tied to workload + deadline proximity
- Algorithm Lab / Analytics module — run your algorithms (search, sort, scheduling) across
  varying input sizes and plot execution time, memory usage, and solution quality; this is
  your "measurable evidence" section from the abstract
- UI polish, full workspace automation, error handling, optional deployment

This split matches how a DSA project is usually graded: mid review = "did you correctly
implement and integrate the structures," final = "did you use them to solve the harder
optimization/adaptive problem, with evidence."

---

## 2. The build prompt (for Claude Code / an AI coding agent)

Copy the block below into Claude Code to scaffold the **mid-review MVP**.

```
You are building the MID-REVIEW MVP of AlgoSync, an algorithm-driven academic productivity
platform. This is for a Data Structures & Algorithms course project, so correctness and
visibility of the underlying data structures matters as much as the UI. Build a working,
end-to-end, runnable system.

IMPORTANT CONSTRAINT
Implement the core data structures YOURSELF (AVL Tree, Trie, Hash Table with explicit
collision handling, Binary Heap, Heapsort) as real classes with insert/delete/search/
traverse methods — do not just wrap Python's built-in dict/heapq/sorted() and call it done.
The point of this project is demonstrating the structures. You may use standard library
data structures only for incidental plumbing (e.g. storing raw file lists before indexing),
never as a substitute for the required structure itself.

ARCHITECTURE
- Backend: Python, FastAPI.
- Data structures live in their own modules: avl_tree.py, trie.py, hash_table.py,
  binary_heap.py, heapsort.py — each independently unit-testable.
- No external database needed for mid-review; in-memory structures are fine (mention this
  as a known limitation / future work item in the README).
- Frontend: React + shadcn/ui (ui.shadcn.com components) + Tailwind, calling the FastAPI
  backend over REST.

MODULES TO IMPLEMENT

1. Task Analyzer
   - On task creation (title, topic, deadline, priority, rough estimated hours), compute
     a simple workload/urgency score (e.g. based on days-to-deadline + estimated hours +
     priority weight). Keep the formula simple and documented — it feeds the heap.

2. AVL Tree (deadline organization)
   - Keyed by deadline (then task id as tiebreaker).
   - Standard insert/delete with rotations (LL, RR, LR, RL), self-balancing.
   - Expose in-order traversal for "tasks sorted by deadline" view.
   - Expose the tree height/balance factor per node for an optional debug view.

3. Hash Table (task/resource lookup)
   - Own implementation with explicit collision handling (chaining or open addressing —
     pick one, document it).
   - O(1) average lookup by task ID and by resource ID.

4. Trie (prefix/keyword search)
   - Insert resource filenames/tags/keywords.
   - Support prefix search (autocomplete) and exact keyword search.
   - Used by the Resource Engine's search endpoint.

5. Binary Max-Heap + Heapsort (prioritization & ranking)
   - Heap ops: insert, extract-max, peek — used as the task priority queue (by workload/
     urgency score from the Task Analyzer) and for Top-K resource retrieval.
   - Heapsort implemented explicitly, used to produce the final ranked resource list
     for display (don't call sorted() here — build it from your heap).

6. Resource Engine
   - Index a given local folder: walk files, extract filename + simple tags (from filename/
     extension/user-entered tags), insert into the Trie and Hash Table.
   - One simple web resource fetch (e.g. hit a public search/education API, or scrape a
     lightweight endpoint) to pull 3-5 supplementary resources per task topic, merged into
     the same ranking pipeline.

7. Workspace Assembly
   - Given a task, pull its ranked resources (via heap/heapsort) into a single "workspace"
     response: task details + top-K resources with scores.

WORKFLOW TO DEMO END-TO-END
1. User creates a task (title, topic, deadline, priority, est. hours) → Task Analyzer scores
   it → task inserted into AVL Tree (by deadline) and Hash Table (by ID) and pushed onto the
   priority Heap.
2. Task list view renders via AVL in-order traversal (sorted by deadline) AND a "priority
   view" via heap peek/extract (sorted by urgency) — show both to prove both structures work.
3. User searches resources for a task topic → query hits the Trie for local matches, plus
   the web fetch for supplementary ones.
4. All candidate resources go through the heap + heapsort ranking pipeline → Top-K returned.
5. Workspace view shows the task + its ranked resources.
6. An "Algorithm Trace" panel in the UI logs each operation as it happens, e.g.
   "AVL insert -> 1 rotation (LL)", "Heap extract-max -> O(log n)", "Trie prefix search ->
   3 matches" — this is the single most convincing thing to show a DSA professor live.

FRONTEND (shadcn/ui)
- Use shadcn components: Card, Tabs, Input, Button, Badge, ScrollArea, Table, Sidebar.
- Pages/sections: (a) Task creation form, (b) Task list (toggle between "by deadline" /
  "by priority"), (c) Resource search with autocomplete, (d) Workspace view per task,
  (e) Algorithm Trace log panel.
- Keep styling clean and functional; the priority here is making the data structures'
  behavior visible and correct, not visual polish.

DELIVERABLES
- Fully runnable backend with a short section in the README on how to run it and how each
  endpoint maps to which data structure.
- Fully runnable frontend.
- Basic unit tests for each data structure module (insert/delete/search correctness,
  AVL balance property held after operations) — professors reviewing a DSA project often
  ask "how do you know it's correct," and tests answer that directly.
- Keep code modular so the Scheduling Engine (Greedy/DP/Backtracking/B&B), Adaptive
  Learning Engine, Reminders, and Algorithm Lab/Analytics can be added later without
  restructuring the data layer.

Build this iteratively: data structure modules + unit tests first, then the FastAPI
endpoints wired to them, then the frontend last.
```

---

## 3. Notes for your mid-review presentation

- Open with the architecture diagram from your abstract, then say explicitly: "today's
  review covers the data layer — AVL, Trie, Hash Table, Heap/Heapsort — the Scheduling
  Engine and Adaptive Learning Engine are the final-review deliverables."
- The **Algorithm Trace panel** is your strongest demo asset — professors grading a DSA
  project want to see the structures doing work, not just a clean UI. Lean on it.
- Have your unit tests ready to show/run live if asked "how do you know the AVL tree stays
  balanced" — running a test that asserts balance factors ∈ {-1,0,1} after a stress-insert
  is a strong, concrete answer.
- If time allows, a tiny before/after comparison (e.g. "Trie prefix search vs. naive linear
  scan over N filenames") previews your final-review Algorithm Lab and shows you're already
  thinking about complexity evidence, not just implementation.

---



# 4. Continuation prompt (for the next phase of work on this codebase)

Everything above this point is the original planning document. Everything in this section is
new — a build prompt in the same style as §2, written for whoever (human or AI agent) picks
this codebase up next. Unlike §2, this is not scaffolding from nothing: KAIROS/AlgoSync is
built, tested (196 tests) and running; treat the existing code as the source of truth over this
document wherever the two disagree, and update the Status section above when you change that.

```
You are continuing work on KAIROS, an already-working algorithm-driven academic productivity
platform (Python/FastAPI backend, hand-written AVL tree / Trie / Hash table / Binary heap /
Heapsort, React/Tailwind/shadcn frontend). Both the mid-review and final-review scope from
this document are implemented and passing 196 tests. Read kairos/README.md and kairos/AUDIT.md
before changing anything — they are the current, accurate description of the system; this
planning document is the historical plan, not the spec to re-implement.

DO NOT re-implement or re-derive the five required data structures, the Scheduling Engine,
the Adaptive Learning Engine, or the Algorithm Lab's time/memory/operation measurement —
they exist, are tested, and the hand-written-structures constraint from the original build
prompt (no dict/heapq/sorted() substituting for the real thing) still applies to anything
you add.

PICK FROM THE KNOWN LIMITATIONS LIST IN README.md — do not invent new scope. In rough order
of value for a student project (highest-leverage first):

1. Real persistence. A JSON snapshot already survives restarts (services/persistence.py).
   The next step is SQLite behind a repository interface, so the store gains durability
   without every module that touches store.py changing — store.py is deliberately the only
   module that talks to all five structures, so this is where a repository interface goes.
2. PDF/DOCX/PPTX content indexing. extract_text_keywords() in resource_engine.py already
   separates "read this file's text" from "tokenise and rank it" — add a parser per format
   that hands back plain text, and the tokenising/ranking/Trie-indexing/scoring pipeline
   needs no changes at all.
3. TF-IDF instead of raw term frequency, so a word common to every indexed file stops
   carrying the same weight as a distinctive one. Needs one corpus-wide document-frequency
   pass over the store's resources; slots into score_resource() as an additional factor.
4. A real quiz/assessment engine behind the Adaptive Learning Engine, replacing the
   self-reported mastery slider — the concept-chain and weighting logic in adaptive.py
   should not need to change, only where the mastery number comes from.
5. Auth + multi-user. Bigger: the store is currently one global singleton. Needs a design
   decision (per-user store instances? a tenant_id on every record?) before touching code —
   raise this as a question rather than guessing.

Whatever you pick: write the tests first or alongside the code (the project's own test
suite is the strongest evidence of correctness a DSA reviewer will ask for — see
"Tests — how do you know it's correct?" in README.md for the standard this project holds
itself to), verify end to end, then update both README.md's Known Limitations and the
Status section at the top of this document so it keeps being an accurate record rather than
drifting back out of sync with the code — that gap is exactly what this section exists to
prevent.
```

---

