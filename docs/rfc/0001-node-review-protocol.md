# RFC 0001 Node Review Protocol

## Round 1: Architecture / Security / Feasibility

Each node writes:

```text
reviews/round1/<node>.md
```

Template:

```markdown
# Round 1 Review - <node>

## Verdict
Approve / Request changes / Block

## Top risks
1.
2.
3.

## What works

## What breaks on this node

## Security concerns

## Confidence
High / Medium / Low
```

## Round 2: Implementation Readiness

Each node writes:

```text
reviews/round2/<node>.md
```

Checks:

1. Can this node execute its assigned responsibilities?
2. Are sync boundaries clear?
3. Are sensitive/private artifacts protected?
4. Does GitHub/misakanet.org degradation work?
5. Should MVP implementation proceed?

## Final decision rule

- 5 nodes total.
- Minimum 4 approvals.
- company-win and company-mac must approve.
- Any critical security concern must be resolved before implementation.
