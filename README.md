# Multi Agent Manager MVP

## Run server

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

Open:
- http://127.0.0.1:8010/dashboard

## Run worker

In another shell:

```bash
source .venv/bin/activate
PYTHONPATH=. python worker/runner.py
```

## Create a task

Use the dashboard form, or:

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
