# RFC 0001: MisakaNet Multi-node Control Plane + Memory Portal

## Summary

Upgrade `multi-agent-manager` from a worker dashboard into the MisakaNet control plane:

- local-first memory bus for company Windows/macOS nodes
- GitHub as sanitized async ledger
- misakanet.org as public memory portal
- private machine as external collector
- cloud Aily as GitHub-only reviewer/consumer

## Target Architecture

```text
company-win / company-mac
  Claude + Codex + mify
  local memory bus
        |
        v
GitHub ledger
  sanitized reviews / roadmap / architecture / node status
        |
        v
misakanet.org public memory portal

private-home
  Hermes / OpenClaw / CodeWhale
  external collector
        |
        v
GitHub + misakanet.org

cloud-aily
  GitHub-only reader/reviewer
```

## Non-goals

- No internal network tunneling.
- No raw enterprise chat/session upload.
- No secret/token/local-path publication.
- No public write endpoint in v0.

## Phases

### Phase 0: RFC review

Run two review rounds across all nodes before implementation.

### Phase 1: Local memory bus

Each company node keeps:

```text
.misaka-memory/
  inbox/
  items/
  reviews/
  decisions/
  roadmap/
  public/
  private/
  manifest.jsonl
  index.sqlite
  sync-state.json
```

### Phase 2: GitHub ledger

GitHub stores only sanitized/public artifacts:

```text
public/
sanitized/
roadmap/
reviews-summary/
```

### Phase 3: misakanet.org portal

Public pages:

```text
/memory
/memory/reviews
/memory/roadmap
/memory/architecture
/memory/nodes
/memory/external
```

### Phase 4: private external collector

Private node collects public external context and publishes digests only.

## Final acceptance criteria

- company-win approves
- company-mac approves
- private-home approves external collector
- cloud-aily confirms GitHub ledger is usable
- misakanet.org confirms public exposure boundary is acceptable
- at least 4/5 nodes approve after round 2
