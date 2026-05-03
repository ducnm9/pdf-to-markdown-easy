---
inclusion: manual
---

# Subagent-Driven Development

Execute plan by dispatching fresh subagent per task, with two-stage review after each: spec compliance review first, then code quality review.

**Why subagents:** Fresh context per task prevents confusion. Precisely crafted instructions ensure focus. Preserves your own context for coordination.

**Core principle:** Fresh subagent per task + two-stage review (spec then quality) = high quality, fast iteration

## When to Use

- Have an implementation plan with mostly independent tasks
- Want to stay in this session
- Tasks can be executed sequentially with review between each

## The Process

1. **Read plan** — extract all tasks with full text, note context
2. **For each task:**
   - Dispatch implementer subagent with full task text + context
   - If subagent asks questions → answer, re-dispatch
   - Subagent implements, tests, commits, self-reviews
   - Dispatch spec reviewer subagent → confirms code matches spec
   - If spec issues → implementer fixes → re-review
   - Dispatch code quality reviewer subagent → approves quality
   - If quality issues → implementer fixes → re-review
   - Mark task complete
3. **After all tasks** — dispatch final code reviewer for entire implementation
4. **Use `#superpowers-finishing-branch`** to complete the work

## Handling Implementer Status

- **DONE:** Proceed to spec compliance review
- **DONE_WITH_CONCERNS:** Read concerns before proceeding. Address correctness/scope issues before review.
- **NEEDS_CONTEXT:** Provide missing context and re-dispatch
- **BLOCKED:** Assess blocker — provide more context, use more capable model, break into smaller pieces, or escalate to user

## Red Flags

**Never:**
- Skip reviews (spec compliance OR code quality)
- Proceed with unfixed issues
- Start code quality review before spec compliance is ✅
- Move to next task while either review has open issues
- Start implementation on main/master branch without explicit user consent

**If subagent asks questions:** Answer clearly and completely
**If reviewer finds issues:** Implementer fixes → reviewer reviews again → repeat until approved
