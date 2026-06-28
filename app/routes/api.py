import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import HeartbeatEvent, MemoryItem, Task, TaskEvent, Worker
from app.schemas import (
    MemoryCreate,
    MemorySyncStatusUpdate,
    TaskCreate,
    TaskPullRequest,
    TaskReport,
    WorkerHeartbeat,
    WorkerRegister,
)

router = APIRouter(prefix="/api", tags=["api"])

MEMORY_TYPES = {"review", "roadmap", "architecture", "decision", "session", "external"}
SENSITIVITY_LEVELS = {"public", "project-public", "internal-summary", "private-local-only", "secret-never-sync"}
SYNC_STATUSES = {"local-only", "ready-for-github", "synced-github", "ready-for-portal", "synced-portal"}
PUBLIC_SENSITIVITY = {"public", "project-public"}
PUBLIC_SYNC_STATUS = {"ready-for-github", "synced-github", "ready-for-portal", "synced-portal"}

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{12,}"),
    re.compile(r"[A-Za-z]:\\[^\s`]+"),
    re.compile(r"\\\\[^\s`]+"),
    re.compile(r"/(?:Users|home|mnt)/[^\s`]+"),
    re.compile(r"(?i)https?://(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[0-1])\.\d+\.\d+|[^\s/]*\.local|[^\s/]*\.internal)\b"),
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def add_event(session: Session, task_id: str, event_type: str, message: str = "") -> None:
    session.add(TaskEvent(task_id=task_id, event_type=event_type, message=message))


def parse_json_list(value: str) -> list[str]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def validate_memory_contract(
    *,
    item_type: str,
    sensitivity: str,
    sync_status: str,
    title: str,
    content: str,
    source_ref: str = "",
    tags_json: str = "[]",
) -> None:
    if item_type not in MEMORY_TYPES:
        raise HTTPException(status_code=400, detail=f"invalid memory type: {item_type}")
    if sensitivity not in SENSITIVITY_LEVELS:
        raise HTTPException(status_code=400, detail=f"invalid sensitivity: {sensitivity}")
    if sync_status not in SYNC_STATUSES:
        raise HTTPException(status_code=400, detail=f"invalid sync_status: {sync_status}")
    if sync_status in PUBLIC_SYNC_STATUS and sensitivity not in PUBLIC_SENSITIVITY:
        raise HTTPException(status_code=400, detail="only public/project-public memory can be marked export-ready")
    if sensitivity in PUBLIC_SENSITIVITY:
        scan_public_content(title, content, source_ref, tags_json)


def scan_public_content(*values: object) -> None:
    text = "\n".join(str(value) for value in values if value)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise HTTPException(status_code=400, detail="public memory content appears to contain a secret, local path, or internal URL")


def memory_to_dict(item: MemoryItem) -> dict[str, Any]:
    return {
        "id": item.memory_id,
        "type": item.type,
        "title": item.title,
        "content": item.content,
        "source_node": item.source_node,
        "source_agent": item.source_agent,
        "source_ref": item.source_ref,
        "tags": parse_json_list(item.tags_json),
        "sensitivity": item.sensitivity,
        "sync_status": item.sync_status,
        "created_at": normalize_dt(item.created_at).isoformat() if item.created_at else None,
        "updated_at": normalize_dt(item.updated_at).isoformat() if item.updated_at else None,
    }


@router.post("/workers/register")
def register_worker(payload: WorkerRegister, session: Session = Depends(get_session)):
    worker = session.exec(select(Worker).where(Worker.worker_id == payload.worker_id)).first()
    if worker is None:
        worker = Worker(
            worker_id=payload.worker_id,
            machine_name=payload.machine_name,
            host_type=payload.host_type,
            agents_json=json.dumps(payload.agents, ensure_ascii=False),
            tags_json=json.dumps(payload.tags, ensure_ascii=False),
            max_concurrency=payload.max_concurrency,
            status="idle",
        )
        session.add(worker)
    else:
        worker.machine_name = payload.machine_name
        worker.host_type = payload.host_type
        worker.agents_json = json.dumps(payload.agents, ensure_ascii=False)
        worker.tags_json = json.dumps(payload.tags, ensure_ascii=False)
        worker.max_concurrency = payload.max_concurrency
        worker.status = "idle"
        worker.updated_at = utcnow()
        worker.last_heartbeat_at = utcnow()
    session.commit()
    return {"ok": True}


@router.post("/workers/heartbeat")
def heartbeat(payload: WorkerHeartbeat, session: Session = Depends(get_session)):
    worker = session.exec(select(Worker).where(Worker.worker_id == payload.worker_id)).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="worker not found")
    worker.current_task_id = payload.current_task_id
    worker.status = payload.status
    worker.app_version = payload.app_version
    worker.last_error_summary = payload.last_error_summary
    worker.requires_manual_intervention = payload.requires_manual_intervention
    worker.last_heartbeat_at = utcnow()
    worker.updated_at = utcnow()
    if payload.last_error_summary:
        worker.last_error_at = utcnow()
    if payload.status in {"idle", "running"} and not payload.last_error_summary:
        worker.last_success_at = utcnow()
    session.add(worker)
    session.add(
        HeartbeatEvent(
            worker_id=payload.worker_id,
            status=payload.status,
            current_task_id=payload.current_task_id,
            load=payload.load,
            app_version=payload.app_version,
            last_error_summary=payload.last_error_summary,
            requires_manual_intervention=payload.requires_manual_intervention,
        )
    )
    session.commit()
    return {"ok": True, "server_time": utcnow().isoformat()}


@router.post("/tasks/create")
def create_task(payload: TaskCreate, session: Session = Depends(get_session)):
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    task = Task(
        task_id=task_id,
        title=payload.title,
        description=payload.description,
        preferred_agent=payload.preferred_agent,
        preferred_worker=payload.preferred_worker,
        input_payload_json=json.dumps(payload.input_payload, ensure_ascii=False),
    )
    session.add(task)
    add_event(session, task_id, "created", "task created")
    session.commit()
    return {"ok": True, "task_id": task_id}


@router.post("/tasks/pull")
def pull_task(payload: TaskPullRequest, session: Session = Depends(get_session)):
    worker = session.exec(select(Worker).where(Worker.worker_id == payload.worker_id)).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="worker not found")

    statement = select(Task).where(Task.status == "pending")
    tasks = session.exec(statement).all()

    selected = None
    for task in tasks:
        if task.preferred_worker and task.preferred_worker != payload.worker_id:
            continue
        if task.preferred_agent and task.preferred_agent not in payload.agents:
            continue
        selected = task
        break

    if selected is None:
        return {"task": None}

    selected.status = "assigned"
    selected.assigned_worker_id = payload.worker_id
    selected.started_at = utcnow()
    worker.current_task_id = selected.task_id
    worker.status = "busy"
    add_event(session, selected.task_id, "assigned", f"assigned to {payload.worker_id}")
    session.add(selected)
    session.add(worker)
    session.commit()

    return {
        "task": {
            "task_id": selected.task_id,
            "title": selected.title,
            "description": selected.description,
            "preferred_agent": selected.preferred_agent,
            "input_payload": json.loads(selected.input_payload_json),
            "timeout_sec": 1800,
        }
    }


@router.post("/tasks/report")
def report_task(payload: TaskReport, session: Session = Depends(get_session)):
    task = session.exec(select(Task).where(Task.task_id == payload.task_id)).first()
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    worker = session.exec(select(Worker).where(Worker.worker_id == payload.worker_id)).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="worker not found")

    task.status = payload.status
    task.result_summary = payload.result_summary
    task.error_summary = payload.error_summary
    task.output_payload_json = json.dumps(payload.output_payload, ensure_ascii=False)
    add_event(session, task.task_id, payload.status, payload.message)

    if payload.status in {"success", "failed", "manual_needed", "cancelled"}:
        task.finished_at = utcnow()
        worker.current_task_id = None
        worker.status = "idle"
    elif payload.status == "running":
        worker.status = "busy"

    session.add(task)
    session.add(worker)
    session.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: str, session: Session = Depends(get_session)):
    task = session.exec(select(Task).where(Task.task_id == task_id)).first()
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    task.status = "pending"
    task.assigned_worker_id = None
    task.started_at = None
    task.finished_at = None
    task.retry_count += 1
    add_event(session, task.task_id, "retried", "task retried")
    session.add(task)
    session.commit()
    return {"ok": True}


@router.post("/memory/items")
def create_memory_item(payload: MemoryCreate, session: Session = Depends(get_session)):
    validate_memory_contract(
        item_type=payload.type,
        sensitivity=payload.sensitivity,
        sync_status=payload.sync_status,
        title=payload.title,
        content=payload.content,
        source_ref=payload.source_ref,
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
    )
    memory = MemoryItem(
        memory_id=f"mem_{uuid.uuid4().hex[:12]}",
        type=payload.type,
        title=payload.title,
        content=payload.content,
        source_node=payload.source_node,
        source_agent=payload.source_agent,
        source_ref=payload.source_ref,
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
        sensitivity=payload.sensitivity,
        sync_status=payload.sync_status,
    )
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return {"ok": True, "item": memory_to_dict(memory)}


@router.get("/memory/items")
def list_memory_items(
    session: Session = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    q: str | None = None,
    source_node: str | None = None,
    item_type: str | None = Query(default=None, alias="type"),
    sync_status: str | None = None,
):
    statement = select(MemoryItem).order_by(MemoryItem.created_at.desc())
    if source_node:
        statement = statement.where(MemoryItem.source_node == source_node)
    if item_type:
        statement = statement.where(MemoryItem.type == item_type)
    if sync_status:
        statement = statement.where(MemoryItem.sync_status == sync_status)
    items = session.exec(statement).all()
    if q:
        needle = q.lower()
        items = [item for item in items if needle in item.title.lower() or needle in item.content.lower() or needle in item.source_ref.lower()]
    return {"items": [memory_to_dict(item) for item in items[:limit]]}


@router.get("/memory/items/{memory_id}")
def get_memory_item(memory_id: str, session: Session = Depends(get_session)):
    item = session.exec(select(MemoryItem).where(MemoryItem.memory_id == memory_id)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="memory item not found")
    return {"item": memory_to_dict(item)}


@router.patch("/memory/items/{memory_id}/sync-status")
def update_memory_sync_status(memory_id: str, payload: MemorySyncStatusUpdate, session: Session = Depends(get_session)):
    item = session.exec(select(MemoryItem).where(MemoryItem.memory_id == memory_id)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="memory item not found")
    validate_memory_contract(
        item_type=item.type,
        sensitivity=item.sensitivity,
        sync_status=payload.sync_status,
        title=item.title,
        content=item.content,
        source_ref=item.source_ref,
        tags_json=item.tags_json,
    )
    item.sync_status = payload.sync_status
    item.updated_at = utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"ok": True, "item": memory_to_dict(item)}


@router.get("/memory/public")
def list_public_memory(session: Session = Depends(get_session), limit: int = Query(default=200, ge=1, le=1000)):
    statement = (
        select(MemoryItem)
        .where(MemoryItem.sensitivity.in_(PUBLIC_SENSITIVITY))
        .where(MemoryItem.sync_status.in_(PUBLIC_SYNC_STATUS))
        .order_by(MemoryItem.created_at.desc())
    )
    items = session.exec(statement).all()[:limit]
    for item in items:
        scan_public_content(item.title, item.content, item.source_ref, item.tags_json)
    return {"items": [memory_to_dict(item) for item in items]}


@router.get("/summary")
def summary(session: Session = Depends(get_session)):
    workers = session.exec(select(Worker)).all()
    tasks = session.exec(select(Task)).all()
    memory_items = session.exec(select(MemoryItem)).all()
    now = utcnow()
    online_count = sum(1 for w in workers if normalize_dt(w.last_heartbeat_at) and normalize_dt(w.last_heartbeat_at) >= now - timedelta(seconds=90))
    return {
        "workers": len(workers),
        "workers_online": online_count,
        "workers_needs_attention": sum(1 for w in workers if w.requires_manual_intervention),
        "tasks_total": len(tasks),
        "tasks_running": sum(1 for t in tasks if t.status in {"assigned", "running"}),
        "tasks_failed": sum(1 for t in tasks if t.status == "failed"),
        "tasks_manual_needed": sum(1 for t in tasks if t.status == "manual_needed"),
        "memory_items": len(memory_items),
        "memory_export_ready": sum(1 for item in memory_items if item.sync_status in PUBLIC_SYNC_STATUS and item.sensitivity in PUBLIC_SENSITIVITY),
    }
