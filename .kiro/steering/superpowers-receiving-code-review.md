---
inclusion: manual
---

# Code Review Reception

Code review requires technical evaluation, not emotional performance.

**Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort.

## The Response Pattern

1. **READ:** Complete feedback without reacting
2. **UNDERSTAND:** Restate requirement in own words (or ask)
3. **VERIFY:** Check against codebase reality
4. **EVALUATE:** Technically sound for THIS codebase?
5. **RESPOND:** Technical acknowledgment or reasoned pushback
6. **IMPLEMENT:** One item at a time, test each

## Forbidden Responses

**NEVER:** "You're absolutely right!", "Great point!", "Let me implement that now" (before verification)

**INSTEAD:** Restate the technical requirement, ask clarifying questions, push back with technical reasoning if wrong, or just start working.

## Handling Unclear Feedback

If any item is unclear: STOP — do not implement anything yet. ASK for clarification on unclear items.

Items may be related. Partial understanding = wrong implementation.

## Source-Specific Handling

### From User
- Trusted — implement after understanding
- Still ask if scope unclear
- Skip to action or technical acknowledgment

### From External Reviewers
Before implementing, check:
1. Technically correct for THIS codebase?
2. Breaks existing functionality?
3. Reason for current implementation?
4. Works on all platforms/versions?

If suggestion seems wrong: Push back with technical reasoning.

## Implementation Order

1. Clarify anything unclear FIRST
2. Then implement: Blocking issues → Simple fixes → Complex fixes
3. Test each fix individually
4. Verify no regressions

## When To Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Conflicts with user's architectural decisions

## Acknowledging Correct Feedback

```
✅ "Fixed. [Brief description of what changed]"
✅ "Good catch - [specific issue]. Fixed in [location]."
✅ [Just fix it and show in the code]

❌ "You're absolutely right!" / "Great point!" / "Thanks for catching that!"
```

Actions speak. Just fix it.
