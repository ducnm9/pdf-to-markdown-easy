---
inclusion: manual
---

# Using Git Worktrees

Git worktrees create isolated workspaces sharing the same repository, allowing work on multiple branches simultaneously.

**Core principle:** Systematic directory selection + safety verification = reliable isolation.

## Directory Selection Process (Priority Order)

1. **Check existing directories:** `.worktrees/` (preferred) or `worktrees/`
2. **Check project config** for worktree directory preference
3. **Ask user** if nothing found

## Safety Verification

For project-local directories: MUST verify directory is git-ignored before creating worktree.

```bash
git check-ignore -q .worktrees 2>/dev/null
```

If NOT ignored: add to .gitignore, commit, then proceed.

## Creation Steps

1. **Detect project name:** `basename "$(git rev-parse --show-toplevel)"`
2. **Create worktree:** `git worktree add "$path" -b "$BRANCH_NAME"`
3. **Run project setup:** Auto-detect (package.json → npm install, Cargo.toml → cargo build, etc.)
4. **Verify clean baseline:** Run tests to ensure worktree starts clean
5. **Report location and test status**

## Quick Reference

| Situation | Action |
|-----------|--------|
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Both exist | Use `.worktrees/` |
| Neither exists | Check config → Ask user |
| Directory not ignored | Add to .gitignore + commit |
| Tests fail during baseline | Report failures + ask |

## Red Flags

**Never:**
- Create worktree without verifying it's ignored (project-local)
- Skip baseline test verification
- Proceed with failing tests without asking
- Assume directory location when ambiguous
