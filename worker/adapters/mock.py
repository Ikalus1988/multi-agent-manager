import time

from worker.adapters.base import BaseAdapter


class MockAdapter(BaseAdapter):
    def run(self, task: dict) -> dict:
        prompt = task.get("input_payload", {}).get("prompt", "")
        time.sleep(2)
        return {
            "status": "success",
            "message": "mock task completed",
            "result_summary": f"mock completed: {prompt[:80]}",
            "output_payload": {"echo": prompt},
        }
