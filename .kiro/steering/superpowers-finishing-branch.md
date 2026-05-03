---
inclusion: manual
---

# Finishing a Development Branch

Guide completion of development work by presenting clear options and handling chosen workflow.

**Core principle:** Verify tests → Present options → Execute choice → Clean up.

## The Process

### Step 1: Verify Tests

Run project's test suite. If tests fail: stop, show failures, fix before proceeding.

### Step 2: Determine Base Branch

```bash
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```

### Step 3: Present Options

Present exactly these 4 options:

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

### Step 4: Execute Choice

**Option 1 — Merge Locally:** Checkout base, pull latest, merge feature branch, verify tests, delete feature branch, cleanup worktree.

**Option 2 — Push and Create PR:** Push branch, create PR with summary and test plan, cleanup worktree.

**Option 3 — Keep As-Is:** Report branch name and worktree path. Don't cleanup.

**Option 4 — Discard:** Confirm first (require typed "discard"), then delete branch and cleanup worktree.

## Red Flags

**Never:**
- Proceed with failing tests
- Merge without verifying tests on result
- Delete work without confirmation
- Force-push without explicit request
