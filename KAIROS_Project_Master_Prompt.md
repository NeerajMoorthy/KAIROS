HISTORICAL MATERIAL — not the current KAIROS v1.0 product specification.

Use the repository root README.md for current product scope and verified implementation behavior.
This document preserves earlier ADSA review/presentation content; prior screens and claims below
are historical context, not current product promises.

---
# KAIROS — Project Master Prompt

Use this document as the canonical context prompt for future project planning, implementation, reviews, reports, presentations, and viva preparation. It is grounded in the project materials available at the time this prompt was prepared. Treat implementation details and progress numbers as claims from the mid-project review deck until verified against the actual repository.

---

## 1. Canonical identity and source-of-truth rules

**Canonical project name: KAIROS**

**Expansion used in the current review:** **K**nowledge **A**cquisition, **I**ndexing, **R**anking & **O**ptimized **S**cheduling.

**Canonical title:** *KAIROS — Knowledge Acquisition, Indexing, Ranking & Optimized Scheduling*

The project materials contain an older document titled **“AlgoSync — Faculty Update & Project Design Prompt.”** It describes an earlier design-stage identity and roadmap. A later document, **“KAIROS_Mid_Review.pptx,”** presents the same academic-productivity project under the KAIROS name and reports a substantially implemented mid-project prototype. Resolve the conflict in favor of **KAIROS**. Use KAIROS in all new and revised project materials. Refer to AlgoSync only when explaining the historical rename; do not treat it as a second product or use it as the current title.

### Evidence boundary

The available project-folder mirror contained no files under `sources/` at the time of review. The two available source documents were the KAIROS mid-project review deck and the older AlgoSync faculty-update prompt attached to the referenced conversation. No code repository, test files, database schema, benchmark output, or runnable application was available for independent inspection. Therefore:

- Treat counts, implementation status, stack details, test results, and benchmark figures below as **reported by the KAIROS review deck**, not independently verified facts.
- Before changing code or publishing a final report, inspect the actual repository and reproduce the relevant claims.
- Do not invent missing requirements, test results, benchmark data, screenshots, user research, or completed features.
- Label information as **reported**, **verified**, **inferred limitation**, or **planned** wherever that distinction matters.

---

## 2. Project purpose and concept

KAIROS is an algorithm-driven academic productivity and adaptive-learning platform. It is intended to turn a student's task, deadline, available study time, existing local study material, and concept mastery into a ranked task workspace and an actionable study plan.

The core chain is:

```text
Academic tasks and deadlines
        ↓
Urgency and workload analysis
        ↓
Local resource indexing and optional web discovery
        ↓
Relevance scoring and Top-K ranking
        ↓
Study-hour allocation and deadline-ordered timeline
        ↓
Progress/mastery tracking
        ↓
Adaptive time allocation and reminders
```

The primary academic objective is to demonstrate how Advanced Data Structures and Algorithms (ADSA) can solve concrete retrieval, prioritisation, ranking, and constrained time-allocation problems. AI or external web services are supporting capabilities; they must not obscure or replace the project's hand-built ADSA core.

---

## 3. Problem statement

Students may already have useful notes, PDFs, slides, and lab materials on their own machines, but those resources are scattered and difficult to retrieve by topic. At the same time, several assignments and exams compete for limited study hours. Generic planners tend to order work by simple dates or user-entered priority, and static timetables do not respond to changes in progress or concept mastery.

**KAIROS problem statement:** Given a student's tasks, deadlines, estimated workload, selected local study material, available study hours, progress, and measured concept mastery, retrieve relevant resources per task, rank urgent work, and allocate study time so that deadlines are addressed while weak concepts receive suitable attention.

This is a project framing from the review materials, not a claim that all competing systems have been exhaustively surveyed.

---

## 4. Objectives

1. Represent tasks ordered by deadline and priority with appropriate data structures.
2. Compute an inspectable urgency score from documented task attributes.
3. Index user-selected local resources for topic and keyword retrieval.
4. Rank local and, where configured, web resources using explicit relevance signals.
5. Compare practical and exact strategies for allocating limited study time.
6. Track topic-level mastery and use it to adjust study-time allocation.
7. Present the behavior of data structures and algorithms in an Algorithm Lab.
8. Validate correctness with tests and compare measured performance against theoretical complexity.
9. Provide an explainable end-to-end demonstration from task entry to adapted study plan.

---

## 5. Reported current state

The KAIROS mid-project review deck reports:

- Approximately **70% complete** at the time of that deck.
- **Python 3** and **FastAPI** for the backend; **React**, **Tailwind CSS**, and **shadcn/ui** for the frontend; REST over JSON.
- **SQLite persistence** as remaining/planned work in the progress timeline. Do not describe SQLite as an already completed persistence layer without repository evidence.
- Five core structures implemented from scratch: AVL tree, binary max-heap, three separate-chaining hash tables, Trie, and Heapsort. The “five structures” count treats the three hash-table instances as one structure family; explain counts consistently.
- Nine algorithms reported as implemented from scratch. The deck describes four scheduling strategies (Greedy, Dynamic Programming, Backtracking, Branch & Bound), Heapsort, plus the core structure operations; verify the intended counting convention in source code before repeating “nine.”
- Seven application screens and 18 REST endpoints.
- 160 unit and integration tests across nine modules, with a reported run of `pytest -q` completing as **160 passed in 2.9 seconds**.
- A local-resource ranking pipeline, web fetching, task workspace, scheduling, adaptive-learning/reminder behavior, Algorithm Lab, and structure-inspection views as reported in the deck.
- Remaining work identified by the deck: SQLite persistence, quiz-based mastery assessment in place of self-reported mastery, memory profiling, final report, documentation, and final demo.

These are **deck-reported status items only**. Verify the working tree, run configuration, feature behavior, tests, screen count, endpoint count, and benchmark reproduction before presenting them as current facts. The older AlgoSync prompt's proposed Java/Spring Boot/PostgreSQL stack is superseded by the later deck's Python/FastAPI/React stack; do not blend the two stacks.

---

## 6. System architecture and module boundaries

Use the following as the reported logical architecture. Confirm actual module names and boundaries from the repository before editing code.

```text
React UI
  ├─ Dashboard / tasks / study plan / resources
  ├─ Algorithm Lab and structure inspection
  └─ REST client (JSON)
          ↓
FastAPI application and API routes
  ├─ Task analysis and urgency scoring
  ├─ Task ordering and priority queues
  ├─ Local resource index and optional web fetch
  ├─ Resource scoring, Top-K, and sorted result presentation
  ├─ Scheduling strategies and timeline creation
  ├─ Concept mastery, adaptation, and reminders
  └─ Benchmark and inspection endpoints/views
          ↓
Hand-built ADSA modules
  ├─ AVL tree keyed by (deadline, task id)
  ├─ Binary max-heap
  ├─ Separate-chaining hash table(s)
  ├─ Trie
  └─ Heapsort
          ↓
File-system references and, when completed, persistent storage
```

Keep clear separation between API/UI orchestration and the hand-built algorithm implementations. Use standard-library or framework facilities where sensible, but do not substitute built-in dictionaries, heaps, or sorting for the algorithm under demonstration on paths whose purpose is to demonstrate that algorithm. Test oracles may use trusted built-ins if the implementation and tests make that boundary clear.

---

## 7. End-to-end workflow

1. A student creates or updates a task with title, topic, deadline, priority, estimated effort, progress, and status.
2. The task analyzer calculates an urgency score and explains its contributing values.
3. KAIROS places the task in deadline and urgency views backed by the reported AVL tree and max-heap.
4. The student explicitly selects local folders. The resource index records permitted metadata such as filename, path, file type, keywords/tags, modification date, and size. Do not scan the whole computer without explicit selection.
5. A Trie supports topic/prefix matching; a hash table hydrates matching resources; a relevance score combines available signals; a heap selects Top-K; Heapsort produces the displayed ordering.
6. Optional web discovery contributes linked candidates with title, URL, source/domain, type, and relevance. Preserve attribution and do not copy complete copyrighted materials.
7. KAIROS builds or displays a task-specific workspace using references to original files where possible.
8. A scheduling strategy chooses tasks that fit the available study-hour capacity. A timeline then lays selected work out earliest-deadline-first and may split work across days.
9. Progress and concept mastery update the learner model. Weak concepts can receive additional study time, revised ordering, and contextual reminders.
10. The Algorithm Lab exposes datasets and choices, runs actual implementations, and shows measured results alongside theoretical complexity.

---

## 8. ADSA mapping and reported algorithm design

| ADSA concept | KAIROS application | Reported complexity/design |
|---|---|---|
| AVL tree | Deadline-ordered task index keyed by `(deadline, task_id)` | Insert/delete/search `O(log n)`; rotations and in-order traversal exposed |
| Binary max-heap | Highest-urgency task and Top-K candidate handling | Peek `O(1)`, insert/extract `O(log n)`, build `O(n)` |
| Hash table | Fast task, resource, and mastery lookup | Separate chaining; reported average lookup `O(1)`, collision handling and rehashing |
| Trie | Prefix/topic lookup for resource names/tags | `O(m + k)` for query length `m` and returned matches `k` as stated in deck |
| Heapsort | Resource ranking and urgency-per-hour ordering | `O(n log n)`, in-place per deck |
| Greedy | Fast approximate selection of tasks by urgency per hour | `O(n log n)` due to ordering; not guaranteed globally optimal |
| Dynamic Programming | Exact 0/1 knapsack allocation | `O(nW)` for discretized capacity `W`; deck uses 0.5-hour granularity |
| Backtracking | Exact include/exclude exploration of task choices | `O(2^n)` worst case; may prune capacity overflow |
| Branch & Bound | Exact best-first scheduling/selection with upper-bound pruning | `O(2^n)` worst case; may explore fewer states in practice |
| Empirical and asymptotic analysis | Algorithm Lab | Explain theoretical growth and report reproducible measurements separately |

### Reported urgency formula

The deck gives:

```text
urgency = 10 × priority_weight
        + 100 / (1 + days_left)
        + 2 × estimated_hours
        + 40 if overdue
```

Treat the formula as review-deck content until the implementation is checked. Confirm units, handling of due-today and overdue tasks, date/time-zone behavior, valid ranges, ties, and user-facing explanation. Do not present its coefficients as empirically validated unless evidence supports that claim.

### Reported adaptive weighting

The deck reports:

```text
weight = (100 − mastery) + 12
```

Weights are normalized over available study hours; concepts below 60% are flagged. Unassessed concepts are described as receiving a 50% allocation estimate without displacing a concept that was assessed poorly. Verify the exact policy in code and tests. Mastery is reportedly self-reported today, with quiz-based assessment still planned.

### Scheduling model and caveats

The review models task selection as 0/1 knapsack: value = urgency, weight = estimated hours, capacity = available study hours. Greedy uses urgency per hour; DP, Backtracking, and Branch & Bound seek an optimum for the same instance. The deck then schedules selected work earliest-deadline-first and can split long tasks across days. Explain that task selection and timeline ordering are distinct stages. State discretization and runtime limitations; exact strategies can grow exponentially.

---

## 9. Feature inventory

### Reported as implemented in the review deck — verify in repository

- Task analyzer with a documented urgency formula.
- AVL deadline ordering, binary max-heap, hash-table family, Trie, and Heapsort.
- Local resource indexing and retrieval.
- Web resource fetching/discovery.
- Resource relevance ranking and task workspace flow.
- Scheduling engine with Greedy, DP, Backtracking, and Branch & Bound.
- Adaptive-learning logic and reminders.
- React application reported to have seven screens.
- FastAPI REST service reported to have 18 endpoints.
- Algorithm Lab with structure inspection and performance demonstrations.
- Tests reported as 160 passing across nine modules.

### Explicitly remaining or planned in the review deck

- SQLite persistence layer.
- Quiz-based concept assessment to replace self-reported mastery.
- Memory profiling.
- Final report and complete documentation.
- Final polished end-to-end demonstration.

Do not silently upgrade any reported or planned feature to verified status. Record current state from direct inspection in a status table before making claims.

---

## 10. Algorithm Lab, tests, and benchmark evidence

The deck describes a live Algorithm Lab and reports these examples:

- Search comparison: 10,000 sorted keys, 200 lookups; AVL reportedly around 100× faster than an unbalanced BST on this ordered input. The BST reportedly reaches height 10,000 while AVL height is 14.
- Sorting at `n = 20,000`: Quicksort 19.8 ms, Merge 35.1 ms, Heapsort 89.4 ms, Insertion 4,496 ms.
- Scheduling at `n = 18`: Branch & Bound reportedly explores 153 states and Backtracking 157,905 for the same optimum.
- Hash behavior: 4,349 collisions across 16,384 buckets, longest chain 6, load factor 0.61.
- Correctness report: 160 tests passed in 2.9 seconds; stress checks include 500 AVL inserts and 300 deletes; scheduler strategies are cross-validated; Greedy has a constructed case where it loses.

These are **reported example values, not independently reproduced results**. Machine-dependent timing must not be presented as a universal performance guarantee. For any benchmark used in a report or viva, record hardware/software, input generation, insertion order, dataset size, repetitions, warm-up policy, timing method, and the exact code revision. Compare equivalent inputs, state what is measured, and separate timing from operation counts, height, collisions, explored states, and solution quality.

When repository access is available, inspect test coverage and run the project's documented test command before relying on the figures. This master prompt does not itself establish that tests have been run.

---

## 11. Research gap, differentiation, and novelty claims

The review deck positions KAIROS at the intersection of adaptive-learning systems and classical ADSA: learner-focused systems may assume curated content, while algorithm demonstrations often lack a student's real task and resource context. It argues for connecting deadlines to the learner's own local repository and making retrieval/allocation algorithms inspectable and measurable.

Present the contribution as a **project-specific integration and educational demonstration**, not as proof that no existing system does this. The proposed differentiators are:

1. An ADSA-first architecture with hand-built structures visible to users.
2. Local academic-resource indexing tied to a task's topic.
3. An explicit retrieval pipeline: topic/prefix match → hash lookup → relevance scoring → heap Top-K → sorted results.
4. Deadline- and workload-aware task prioritisation.
5. Mastery-aware reallocation of limited study time.
6. A built-in lab that compares correctness, structural behavior, and measured performance.

The older AlgoSync prompt also cautions against claiming that the broad productivity/adaptive-learning concept is wholly novel. Any final literature gap must be supported by a current, documented literature search and properly checked references. The deck includes references on AVL trees, algorithms, tries, inverted files, adaptive learning, study planning, and knapsack; verify bibliographic details and claims before submission.

---

## 12. Limitations and risks to discuss honestly

The review materials imply or directly identify the following limits; check which remain applicable:

- Persistence is listed as unfinished, so durable task, resource, and mastery storage may be absent.
- Mastery is reportedly self-reported; quiz-based measurement is planned.
- Ranking and urgency depend on hand-chosen weights and tags/metadata; relevance may be imperfect and coefficients are not shown as user-study validated.
- The local index is described around filenames and tags. Do not imply semantic understanding of full document contents unless the implementation proves it.
- Web discovery depends on external sources and availability; link quality, attribution, and failures need handling.
- DP uses discretized study time; granularity affects accuracy and runtime.
- Backtracking and Branch & Bound have exponential worst-case behavior.
- Benchmarks are machine- and input-dependent; a single result does not establish general superiority.
- Local path indexing must respect user-selected scope, privacy, inaccessible files, duplicate paths, and filesystem changes.
- The project-folder mirror did not include source code, so the reported implementation and figures were not independently validated in this review.

Do not imply user-study validation, production-grade reliability, or generalized learning efficacy without evidence.

---

## 13. Technology stack

**Current stack reported by the KAIROS deck:**

- Backend: Python 3, FastAPI, REST/JSON.
- Frontend: React, Tailwind CSS, shadcn/ui.
- Persistence: SQLite shown as a remaining implementation item.
- Core structures and algorithms: implemented manually in Python according to the deck.
- Tests: pytest is named in the deck.

The older AlgoSync design prompt proposed Java 17+, Spring Boot, PostgreSQL, and Vite/TypeScript. This was an earlier proposal and conflicts with the later KAIROS implementation description. Treat it as superseded unless the actual repository demonstrates a deliberate migration. Do not mix Java/Spring/PostgreSQL assumptions into KAIROS documentation without confirming such a change.

---

## 14. Suggested final demonstration and viva flow

Use one coherent scenario, and only demonstrate screens that actually work:

1. Create **“ADSA Lab — AVL Tree”** with a Friday 5 PM deadline, five estimated hours, and a priority.
2. Show its urgency breakdown and where it appears in the deadline and priority views.
3. Select a sample local course folder and retrieve relevant AVL materials; explain the Trie and hash-table roles.
4. Add or display linked web resources if the integration is available; show their source and relevance reason.
5. Show the ranked Top-K list and explain heap selection and final ordering.
6. Generate a study allocation with a stated available-hour budget. Compare Greedy with an exact strategy; explain when exact results cost more computation.
7. Show the earliest-deadline-first timeline and any split sessions.
8. Update mastery/progress for a concept such as Rotations; show weak-area reallocation and reminder behavior. Explain whether mastery is self-reported or quiz-assessed in the demonstrated build.
9. Open the Algorithm Lab and reproduce one benchmark with its input settings and measured output.
10. Show a relevant correctness test or structure inspection view, and close with limitations and remaining roadmap.

### Likely viva questions to prepare

- Why AVL instead of an ordinary BST for deadline ordering?
- Why use both a heap and an AVL tree, and what operations does each support?
- How are hash collisions handled and when does rehashing occur?
- What does the Trie index, and what are `m` and `k` in the stated complexity?
- How is relevance scored and how are ties made deterministic?
- What exact optimization problem does the scheduler solve? What do value, weight, capacity, and granularity mean?
- Why can Greedy fail to find the optimum? Why do exact methods become expensive?
- How is learner mastery obtained and how does it change the schedule?
- How are benchmark inputs generated and how can results be reproduced?
- Which claims are implemented, tested, measured, or only planned?

---

## 15. Development roadmap

Use this as a verification-led roadmap, not as a claim that every previous phase is complete:

1. **Repository audit:** identify the actual stack, module map, current branch, executable setup, feature status, test command, and discrepancies with the deck.
2. **Core ADSA correctness:** verify AVL, heap, hash table, Trie, and Heapsort invariants, edge cases, deterministic tie behavior, and complexity explanations.
3. **Task and resource integration:** verify task lifecycle, selected-folder indexing, metadata refresh, ranking pipeline, and API/UI behavior.
4. **Scheduling:** verify identical input instances across strategies, objective/capacity definitions, DP granularity, tie behavior, and exact/approximate result labels.
5. **Adaptive learning and reminders:** validate mastery ranges, unknown concepts, weak-area policy, time normalization, and clear explanations.
6. **Persistence:** implement and verify SQLite persistence and migrations if still absent; test restart behavior and data integrity.
7. **Quiz-based mastery:** add assessment-based updates if in scope; explain scoring and avoid overstating learning outcomes.
8. **Quality and profiling:** run existing tests, add or update tests only as part of authorized implementation work, profile memory, and address confirmed defects.
9. **Reproducible Algorithm Lab:** document benchmark controls and regenerate all final figures on the delivered code.
10. **Documentation and final report:** align architecture, algorithms, complexity, test evidence, measured results, limitations, references, and screenshots with the actual build.
11. **Final demo/viva rehearsal:** rehearse the same end-to-end path on a clean setup and prepare concise explanations of trade-offs.

Maintain a status matrix with **Verified complete / Implemented but not verified / In progress / Planned / Out of scope**. Do not assign a completion percentage from intuition; define the denominator and evidence first. The deck's approximately 70% figure is a historical report, not a verified current percentage.

---

## 16. Instructions for future coding or writing agents

When asked to continue KAIROS work:

1. Use **KAIROS** as the only current project identity.
2. Inspect the actual repository and project instructions before editing. Preserve user files and respect any read-only source directories.
3. Establish the real current state from code, tests, configuration, and runnable behavior. Compare it with this prompt and report discrepancies.
4. Do not assume the deck's 70% estimate, stack, feature counts, test count, endpoint count, benchmark values, or timeline remain current.
5. Keep the implementation algorithmically explicit where ADSA learning is the purpose. Explain each structure's real use case, complexity, and limits.
6. Keep retrieval, scoring, scheduling, and adaptation deterministic and inspectable unless the user explicitly changes that requirement.
7. Never fabricate measurements or claim external research proves a universal novelty statement.
8. Separate code-verified facts from design intent, historical claims, and future work in every report.
9. Before calling the project complete, verify the full task-to-resource-to-ranking-to-schedule-to-adaptation workflow and document remaining limitations.

**Canonical final identity:** KAIROS — Knowledge Acquisition, Indexing, Ranking & Optimized Scheduling.

---

## 17. Later local-folder evidence (7 October 2026)

A subsequent inspection found a substantial local implementation under `C:\Users\moort\SEM THREE\ADSA\kairos`, including backend and frontend source, tests, a README, and an audit report. An `algosync` folder beside it contains an older, smaller implementation with overlapping modules. The newer KAIROS folder includes additional scheduling, adaptive-learning, reminders, persistence, benchmark, and UI modules. The old folder's distinct trace panel is described in the current project notes as deliberately removed, so the old code is not required to remain as a separate project.

The local project documents do not agree on the latest status:

- `ADSA.md` reports 196 automated tests, JSON snapshot persistence, and roughly 98% completion against that specification.
- `AUDIT.md` is dated 23 September 2026 and reports 187 tests, no persistence, and roughly 98% against an earlier audit snapshot.
- The older KAIROS mid-project review deck reports 160 tests and about 70% completion.

These figures likely reflect different snapshots and changed requirements. They were not rerun or reconciled while organizing the files. For current claims, check the actual source, test configuration, persistence module, and dated documentation; state which snapshot the evidence comes from. Do not use the mid-review deck's 70% as the current completion estimate.

