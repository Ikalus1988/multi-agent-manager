import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request_json(url, method="GET", payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def test_memory_api_and_export(tmp_path):
    db_path = tmp_path / "app.db"

    port = 8765
    env = os.environ.copy()
    env["MAM_DB_PATH"] = str(db_path)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(40):
            try:
                request_json(f"{base}/api/summary")
                break
            except Exception:
                time.sleep(0.25)
        else:
            stdout, stderr = proc.communicate(timeout=1)
            raise AssertionError(f"server did not start\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")

        private_item = request_json(
            f"{base}/api/memory/items",
            method="POST",
            payload={
                "type": "decision",
                "title": "Keep raw sessions local",
                "content": "Only sanitized summaries may leave the local machine.",
                "source_node": "company-win",
                "source_agent": "codex",
            },
        )["item"]
        assert private_item["sensitivity"] == "private-local-only"
        assert private_item["sync_status"] == "local-only"

        search = request_json(f"{base}/api/memory/items?q=sessions")
        assert len(search["items"]) == 1

        try:
            request_json(
                f"{base}/api/memory/items/{private_item['id']}/sync-status",
                method="PATCH",
                payload={"sync_status": "ready-for-github"},
            )
        except HTTPError as exc:
            assert exc.code == 400
        else:
            raise AssertionError("private memory should not be export-ready")

        request_json(
            f"{base}/api/memory/items",
            method="POST",
            payload={
                "type": "roadmap",
                "title": "Memory MVP",
                "content": "Append and search sanitized collaboration notes.",
                "source_node": "company-win",
                "source_agent": "codex",
                "sensitivity": "project-public",
                "sync_status": "ready-for-github",
            },
        )

        try:
            request_json(
                f"{base}/api/memory/items",
                method="POST",
                payload={
                    "type": "roadmap",
                    "title": "Bad public item",
                    "content": "token=abcdef1234567890",
                    "source_node": "company-win",
                    "sensitivity": "public",
                    "sync_status": "ready-for-github",
                },
            )
        except HTTPError as exc:
            assert exc.code == 400
        else:
            raise AssertionError("public memory should reject token-like content")

        public_items = request_json(f"{base}/api/memory/public")["items"]
        assert len(public_items) == 1
        assert public_items[0]["title"] == "Memory MVP"

        out_dir = tmp_path / "memory"
        subprocess.check_call([sys.executable, "scripts/export_memory.py", "--api-base", base, "--output-dir", str(out_dir)])
        exported = (out_dir / "items.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(exported) == 1
        index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
        assert index["count"] == 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
