<!-- agentic-contract: template_version=6 config_checksum=68cc903945171dee -->
# Multi-Agent Operating Model

## 1. Three nested loops

### Product loop

```text
production evidence -> user/claude product decision -> product contract
```

The user owns value and business context. The Observer role may collect and
summarize feedback, but it may not approve a product direction.

### Engineering loop

```text
frozen WP -> kimi (provider: deepseek) implementation -> tests -> repair -> claude (provider: deepseek) review
```

This loop may run autonomously only inside approved scope and risk boundaries.

### Consultation loop

```text
architecture/incident question -> codex (provider: deepseek) independent analysis -> claude decision
```

codex (provider: deepseek) advice does not silently change the product contract. Material scope
or behavior changes return to the user.

## 2. Gates

| Gate | Owner | Required evidence |
|---|---|---|
| Product Ready | User + claude | problem, value, scope, non-scope, measurable acceptance |
| Architecture Ready | claude; codex (provider: deepseek) when triggered | boundaries, data/time semantics, migration, rollback, test design |
| WP Approved | claude; user for material risk | tracked brief/status, branch/worktree, frozen acceptance tests |
| Ready for Review | kimi (provider: deepseek) | diff, exact tests, commit, risks, no production mutation |
| Approved for Merge | claude | independent diff review and rerun evidence |
| Plan Ready to Merge | claude | every WP in the plan is MERGED into the integration branch |
| Plan Merged | claude | single plan merge commit recorded via `agentic plan finalize` |
| Production Ready | User | replay/shadow evidence, rollback, release checklist |

Passing a later gate never excuses missing evidence from an earlier gate.

One plan converges into one merge commit: WPs merge (no-ff) into the plan's
integration branch; `agentic plan merge` + `agentic plan finalize` collapse the
whole plan into a single merge commit on the target branch, and push happens
exactly once afterwards. See `AGENTS.md` §4.3.

## 3. Consultation triggers

Consult the codex (provider: deepseek) role when any of the following applies:

- cross-package architecture or dependency direction changes;
- scoring, valuation, schema, migration, or point-in-time data semantics change;
- concurrency, cron idempotency, duplicate delivery, security, or corruption risk;
- two repair attempts fail for the same root cause;
- tests pass while production behavior remains unexplained;
- the claude has two materially different designs without decisive evidence.

The consultation request must contain one bounded question, relevant files,
constraints, and the required decision format. Record accepted and rejected
recommendations with reasons.

## 4. Autonomous-loop budget

A kimi (provider: deepseek) may continue without user input while all are true:

- the WP remains within approved scope and allowed paths;
- no production write, real notification, or irreversible action is needed;
- failures are covered by the WP acceptance contract;
- no signal semantics or test expectation must be changed.

The default repair budget is two attempts per root cause. More attempts require
the claude to explain what new evidence justifies continuing.

## 5. Status ownership

- The claude creates and transitions `DRAFT`, `APPROVED`, and `DISPATCHED`.
- The actual kimi (provider: deepseek) transitions `DISPATCHED -> IMPLEMENTING` and records
  executor/session evidence.
- The kimi (provider: deepseek) may set `READY_FOR_REVIEW` or `BLOCKED`.
- The claude alone sets `CHANGES_REQUESTED` or `APPROVED_FOR_MERGE`.
- The merge owner sets `MERGED` after destination-branch verification.
- The user-authorized release owner sets `RELEASED`.

Every transition updates `timestamps.updated_at`. Claims unsupported by Git or
test evidence must be corrected rather than propagated.

## 6. Model handoff contract

Each handoff answers:

```text
What is the frozen objective?
What changed?
What evidence proves it?
What remains uncertain?
What action is requested from the next role?
```

Do not transfer the entire conversation. Transfer the smallest self-contained
artifact that allows the next role to act correctly.

## 7. Production feedback evolution

The target progression is:

1. The Observer role collects runtime metrics and explicit feedback.
2. The Observer role produces candidate issues with supporting evidence.
3. The claude clusters and evaluates candidates against product value.
4. The user authorizes an iteration.
5. The engineering and consultation loops run.
6. A shadow release compares old and new behavior.
7. The user authorizes cutover; the Observer role measures the outcome.

Do not collapse this into "the observer observed a problem, therefore it changed
and deployed code." Observation, product decision, implementation, review, and
release remain separate authorities.
