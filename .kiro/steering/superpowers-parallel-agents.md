---
inclusion: manual
---

# Dispatching Parallel Agents

When you have multiple unrelated failures or independent tasks, investigating them sequentially wastes time. Each investigation is independent and can happen in parallel.

**Core principle:** Dispatch one agent per independent problem domain. Let them work concurrently.

## When to Use

- 2+ independent tasks or failures
- Each problem can be understood without context from others
- No shared state between investigations

**Don't use when:**
- Failures are related (fix one might fix others)
- Need to understand full system state
- Agents would interfere with each other (editing same files)

## The Pattern

### 1. Identify Independent Domains
Group failures by what's broken. Each domain is independent.

### 2. Create Focused Agent Tasks
Each agent gets:
- **Specific scope:** One test file or subsystem
- **Clear goal:** Make these tests pass
- **Constraints:** Don't change other code
- **Expected output:** Summary of what you found and fixed

### 3. Dispatch in Parallel
All agents run concurrently.

### 4. Review and Integrate
- Read each summary
- Verify fixes don't conflict
- Run full test suite
- Integrate all changes

## Agent Prompt Structure

Good agent prompts are:
1. **Focused** — One clear problem domain
2. **Self-contained** — All context needed to understand the problem
3. **Specific about output** — What should the agent return?

## Common Mistakes

- **❌ Too broad:** "Fix all the tests" → agent gets lost
- **✅ Specific:** "Fix agent-tool-abort.test.ts" → focused scope
- **❌ No context:** "Fix the race condition" → agent doesn't know where
- **✅ Context:** Paste the error messages and test names
- **❌ No constraints:** Agent might refactor everything
- **✅ Constraints:** "Do NOT change production code"

## Verification

After agents return:
1. Review each summary
2. Check for conflicts
3. Run full suite
4. Spot check — agents can make systematic errors
