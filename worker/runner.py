import json
import socket
import time
from pathlib import Path

import httpx

from worker.adapters.mock import MockAdapter

BASE_URL = "http://127.0.0.1:8010"
CONFIG = {
    "worker_id": "hp-c-mock",
    "machine_name": socket.gethostname(),
    "host_type": "wsl",
    "agents": ["mock", "cc", "hermes"],
    "tags": ["company-net", "hp", "wsl"],
    "max_concurrency": 1,
    "app_version": "0.1.0",
}


def register(client: httpx.Client) -> None:
    client.post(f"{BASE_URL}/api/workers/register", json=CONFIG).raise_for_status()


def heartbeat(
    client: httpx.Client,
    status: str = "idle",
    current_task_id: str | None = None,
    last_error_summary: str = "",
    requires_manual_intervention: bool = False,
) -> None:
    client.post(
        f"{BASE_URL}/api/workers/heartbeat",
        json={
            "worker_id": CONFIG["worker_id"],
            "current_task_id": current_task_id,
            "load": 0,
            "status": status,
            "app_version": CONFIG["app_version"],
            "last_error_summary": last_error_summary,
            "requires_manual_intervention": requires_manual_intervention,
        },
    ).raise_for_status()


def pull_task(client: httpx.Client):
    response = client.post(
        f"{BASE_URL}/api/tasks/pull",
        json={
            "worker_id": CONFIG["worker_id"],
            "agents": CONFIG["agents"],
            "tags": CONFIG["tags"],
        },
    )
    response.raise_for_status()
    return response.json().get("task")


def report(client: httpx.Client, payload: dict) -> None:
    client.post(f"{BASE_URL}/api/tasks/report", json=payload).raise_for_status()


def run_forever() -> None:
    adapter = MockAdapter()
    with httpx.Client(timeout=30) as client:
        register(client)
        while True:
            heartbeat(client)
            task = pull_task(client)
            if not task:
                time.sleep(3)
                continue

            report(
                client,
                {
                    "task_id": task["task_id"],
                    "worker_id": CONFIG["worker_id"],
                    "status": "running",
                    "message": "mock adapter started",
                },
            )
            heartbeat(client, status="running", current_task_id=task["task_id"])
            result = adapter.run(task)
            report(
                client,
                {
                    "task_id": task["task_id"],
                    "worker_id": CONFIG["worker_id"],
                    "status": result["status"],
                    "message": result["message"],
                    "result_summary": result.get("result_summary", ""),
                    "error_summary": result.get("error_summary", ""),
                    "output_payload": result.get("output_payload", {}),
                },
            )
            heartbeat(
                client,
                status="needs_attention" if result["status"] in {"failed", "manual_needed"} else "idle",
                last_error_summary=result.get("error_summary", ""),
                requires_manual_intervention=result["status"] in {"failed", "manual_needed"},
            )
            time.sleep(1)


if __name__ == "__main__":
    run_forever()
