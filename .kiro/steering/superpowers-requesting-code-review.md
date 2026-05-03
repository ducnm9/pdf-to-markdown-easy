---
inclusion: manual
---

# Requesting Code Review

Dispatch a code review to catch issues before they cascade.

**Core principle:** Review early, review often.

## When to Request Review

**Mandatory:**
- After each task in subagent-driven development
- After completing major feature
- Before merge to main

**Optional but valuable:**
- When stuck (fresh perspective)
- Before refactoring (baseline check)
- After fixing complex bug

## How to Request

1. **Get git SHAs:**
```bash
BASE_SHA=$(git rev-parse HEAD~1)  # or origin/main
HEAD_SHA=$(git rev-parse HEAD)
```

2. **Dispatch code review** with:
   - What was implemented
   - Plan or requirements it should meet
   - Base and head SHAs
   - Brief description

3. **Act on feedback:**
   - Fix Critical issues immediately
   - Fix Important issues before proceeding
   - Note Minor issues for later
   - Push back if reviewer is wrong (with reasoning)

## Red Flags

**Never:**
- Skip review because "it's simple"
- Ignore Critical issues
- Proceed with unfixed Important issues
- Argue with valid technical feedback

**If reviewer wrong:**
- Push back with technical reasoning
- Show code/tests that prove it works
