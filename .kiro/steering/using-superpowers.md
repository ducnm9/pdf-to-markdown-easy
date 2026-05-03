---
inclusion: auto
---

# Superpowers — Development Methodology

You have access to a set of development skills from the Superpowers methodology. These skills guide how you approach tasks — from brainstorming through implementation to completion.

## Instruction Priority

1. **User's explicit instructions** — highest priority
2. **Superpowers skills** — override default behavior where they conflict
3. **Default system prompt** — lowest priority

## Available Skills (use `#` to activate)

| Skill | When to Use |
|-------|-------------|
| `#superpowers-brainstorming` | Before any creative work — creating features, building components, modifying behavior |
| `#superpowers-writing-plans` | When you have a spec/requirements for a multi-step task, before touching code |
| `#superpowers-executing-plans` | When you have a written implementation plan to execute |
| `#superpowers-subagent-driven-development` | When executing implementation plans with independent tasks |
| `#superpowers-tdd` | When implementing any feature or bugfix, before writing implementation code |
| `#superpowers-systematic-debugging` | When encountering any bug, test failure, or unexpected behavior |
| `#superpowers-verification` | When about to claim work is complete, fixed, or passing |
| `#superpowers-requesting-code-review` | When completing tasks, implementing major features, or before merging |
| `#superpowers-receiving-code-review` | When receiving code review feedback |
| `#superpowers-finishing-branch` | When implementation is complete and you need to integrate the work |
| `#superpowers-git-worktrees` | When starting feature work that needs isolation |
| `#superpowers-parallel-agents` | When facing 2+ independent tasks that can be worked on without shared state |

## NO SPEC Default

**When using Superpowers, do NOT suggest creating a spec by default.** Follow the Superpowers flow directly — brainstorm → plan → execute. Specs are a separate Kiro feature and should only be used if the user explicitly asks for one. Stay in the Superpowers methodology.

## The Rule

**Invoke relevant skills BEFORE any response or action.** Even a 1% chance a skill might apply means you should check it.

## Skill Priority

1. **Process skills first** (brainstorming, debugging) — these determine HOW to approach the task
2. **Implementation skills second** — these guide execution

## Red Flags — You're Rationalizing If You Think:

- "This is just a simple question" — Questions are tasks. Check for skills.
- "I need more context first" — Skill check comes BEFORE clarifying questions.
- "This doesn't need a formal skill" — If a skill exists, use it.
- "The skill is overkill" — Simple things become complex. Use it.

## Core Philosophy

- **Test-Driven Development** — Write tests first, always
- **Systematic over ad-hoc** — Process over guessing
- **YAGNI ruthlessly** — Remove unnecessary features
- **Evidence over claims** — Verify before declaring success
