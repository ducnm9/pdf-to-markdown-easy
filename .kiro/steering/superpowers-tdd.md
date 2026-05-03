---
inclusion: manual
---

# Test-Driven Development (TDD)

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over. No exceptions.

## Red-Green-Refactor

### RED — Write Failing Test

Write one minimal test showing what should happen.

**Requirements:**
- One behavior per test
- Clear name describing behavior
- Real code (no mocks unless unavoidable)

### Verify RED — Watch It Fail (MANDATORY)

Run the test. Confirm:
- Test fails (not errors)
- Failure message is expected
- Fails because feature missing (not typos)

**Test passes?** You're testing existing behavior. Fix test.

### GREEN — Minimal Code

Write simplest code to pass the test. Don't add features, refactor other code, or "improve" beyond the test.

### Verify GREEN — Watch It Pass (MANDATORY)

Run the test. Confirm:
- Test passes
- Other tests still pass
- Output pristine (no errors, warnings)

**Test fails?** Fix code, not test.

### REFACTOR — Clean Up

After green only: remove duplication, improve names, extract helpers. Keep tests green. Don't add behavior.

### Repeat

Next failing test for next feature.

## Why Order Matters

- **"I'll write tests after"** — Tests written after pass immediately. Passing immediately proves nothing.
- **"Deleting X hours of work is wasteful"** — Sunk cost fallacy. Working code without real tests is technical debt.
- **"TDD is dogmatic"** — TDD IS pragmatic. Finds bugs before commit, prevents regressions, documents behavior, enables refactoring.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Need to explore first" | Fine. Throw away exploration, start with TDD. |
| "Test hard = design unclear" | Hard to test = hard to use. Listen to the test. |
| "TDD will slow me down" | TDD faster than debugging. |

## Red Flags — STOP and Start Over

- Code before test
- Test after implementation
- Test passes immediately
- Can't explain why test failed
- Rationalizing "just this once"

**All of these mean: Delete code. Start over with TDD.**

## Verification Checklist

Before marking work complete:
- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Each test failed for expected reason
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass
- [ ] Output pristine
- [ ] Tests use real code (mocks only if unavoidable)
- [ ] Edge cases and errors covered
