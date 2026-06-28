# Multi Agent Manager

一个面向跨设备 Agent 运行状态查看和协作记忆沉淀的轻量控制台。

目标：
- 在网页/手机查看设备和 agent 状态
- 设备仅通过出站请求上报状态
- 发现异常后，由用户通过向日葵或 Termius 人工处理
- 心跳和状态上报不调用 LLM，不消耗 token
- 提供本地优先的多 agent 协作记忆层

## Run server

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

Open:
- http://127.0.0.1:8010/dashboard
- http://127.0.0.1:8010/workers
- http://127.0.0.1:8010/memory

## Memory MVP

默认记忆只存在本机 SQLite。只有显式标记为 `public` / `project-public` 且
`ready-for-github` / `ready-for-portal` 的条目才会出现在公开导出里。

Create a local memory item:

```bash
curl -X POST http://127.0.0.1:8010/api/memory/items \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "decision",
    "title": "Keep raw sessions local",
    "content": "Only sanitized summaries may be exported.",
    "source_node": "company-win",
    "source_agent": "codex"
  }'
```

Search memory:

```bash
curl 'http://127.0.0.1:8010/api/memory/items?q=sessions'
```

Export public/project-public memory for GitHub or misakanet.org:

```bash
python scripts/export_memory.py --api-base http://127.0.0.1:8010 --output-dir public/memory
```

Export files:
- `public/memory/items.jsonl`
- `public/memory/index.json`

## Run watcher

In another shell:

```bash
source .venv/bin/activate
PYTHONPATH=. python worker/runner.py
```

The watcher will:
- register itself
- send heartbeats every few seconds
- report running status when it picks a task
- mark `needs_attention` when a task fails or needs manual handling

## Create a task

Use the API directly:

```bash
curl -X POST http://127.0.0.1:8010/api/tasks/create \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "test task",
    "description": "demo",
    "preferred_agent": "mock",
    "input_payload": {"prompt": "hello from hp wsl"}
  }'
```

## Current MVP pages

### Dashboard
- devices total
- devices online
- needs attention count
- tasks running
- memory item count
- export-ready memory count

### Memory
- recent local memory items
- sensitivity and sync status
- quick API reference

### Device detail
- host info
- current state
- current task
- app version
- last success / last error
- recent heartbeat history

## Current status model
- `idle`
- `running`
- `error`
- `needs_attention`
- `offline` (derived by stale heartbeat)

## Manual intervention

When a device is `needs_attention`, `error`, or `offline`, handle it manually with:
- 向日葵
- Termius
