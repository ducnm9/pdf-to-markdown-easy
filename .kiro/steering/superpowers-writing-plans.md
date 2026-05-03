---
inclusion: manual
---

# Writing Plans

Write comprehensive implementation plans assuming the engineer has zero context for the codebase. Document everything: which files to touch, code, testing, docs to check, how to test. Bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

**Save plans to:** `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`

## Scope Check

If the spec covers multiple independent subsystems, suggest breaking into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified. Design units with clear boundaries and well-defined interfaces. Prefer smaller, focused files.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" — step
- "Run it to make sure it fails" — step
- "Implement the minimal code to make the test pass" — step
- "Run the tests and make sure they pass" — step
- "Commit" — step

## Plan Document Header

```markdown
# [Feature Name] Implementation Plan

**Goal:** [One sentence describing what this builds]
**Architecture:** [2-3 sentences about approach]
**Tech Stack:** [Key technologies/libraries]

---
```

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**
```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**
```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## No Placeholders

Every step must contain actual content. These are plan failures — never write them:
- "TBD", "TODO", "implement later"
- "Add appropriate error handling"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code)
- Steps that describe what to do without showing how

## Self-Review

After writing the complete plan:
1. **Spec coverage:** Can you point to a task for each spec requirement?
2. **Placeholder scan:** Search for red flags from the "No Placeholders" section
3. **Type consistency:** Do types, method signatures, and property names match across tasks?

Fix any issues inline.

## Execution Handoff

After saving the plan, offer execution choice:

> "Plan complete and saved. Two execution options:
> 1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks
> 2. **Inline Execution** — execute tasks in this session with checkpoints
>
> Which approach?"
