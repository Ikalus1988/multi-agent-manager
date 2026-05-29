from typing import Any, Optional

from pydantic import BaseModel, Field


class WorkerRegister(BaseModel):
    worker_id: str
    machine_name: str
    host_type: str
    agents: list[str]
    tags: list[str] = Field(default_factory=list)
    max_concurrency: int = 1


class WorkerHeartbeat(BaseModel):
    worker_id: str
    current_task_id: Optional[str] = None
    load: int = 0
    status: str = "idle"


class TaskPullRequest(BaseModel):
    worker_id: str
    agents: list[str]
    tags: list[str] = Field(default_factory=list)


class TaskReport(BaseModel):
    task_id: str
    worker_id: str
    status: str
    message: str = ""
    progress: Optional[int] = None
    result_summary: str = ""
    error_summary: str = ""
    output_payload: dict[str, Any] = Field(default_factory=dict)


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    preferred_agent: Optional[str] = None
    preferred_worker: Optional[str] = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
