# Multi Agent Manager

一个面向跨设备 Agent 运行状态查看的轻量控制台。

目标：
- 在网页/手机查看设备和 agent 状态
- 设备仅通过出站请求上报状态
- 发现异常后，由用户通过向日葵或 Termius 人工处理
- 心跳和状态上报不调用 LLM，不消耗 token

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
- device list with current state and last error

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
