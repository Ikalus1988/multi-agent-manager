from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Worker(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    worker_id: str = Field(index=True, unique=True)
    machine_name: str
    host_type: str
    agents_json: str
    tags_json: str = "[]"
    max_concurrency: int = 1
    status: str = "offline"
    current_task_id: Optional[str] = None
    app_version: str = ""
    last_error_summary: str = ""
    last_error_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    requires_manual_intervention: bool = False
    last_heartbeat_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class HeartbeatEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    worker_id: str = Field(index=True)
    status: str
    current_task_id: Optional[str] = None
    load: int = 0
    app_version: str = ""
    last_error_summary: str = ""
    requires_manual_intervention: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(index=True, unique=True)
    title: str
    description: str = ""
    status: str = Field(default="pending", index=True)
    preferred_agent: Optional[str] = None
    preferred_worker: Optional[str] = None
    input_payload_json: str = "{}"
    output_payload_json: str = "{}"
    result_summary: str = ""
    error_summary: str = ""
    assigned_worker_id: Optional[str] = None
    retry_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class TaskEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(index=True)
    event_type: str
    message: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class MemoryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    memory_id: str = Field(index=True, unique=True)
    type: str = Field(index=True)
    title: str
    content: str
    source_node: str = Field(index=True)
    source_agent: str = ""
    source_ref: str = ""
    tags_json: str = "[]"
    sensitivity: str = Field(default="private-local-only", index=True)
    sync_status: str = Field(default="local-only", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
