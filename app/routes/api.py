import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Task, TaskEvent, Worker
from app.schemas import TaskCreate, TaskPullRequest, TaskReport, WorkerHeartbeat, WorkerRegister

router = APIRouter(prefix="/api", tags=["api"])


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
    worker.last_heartbeat_at = utcnow()
    worker.updated_at = utcnow()
    session.add(worker)
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


@router.get("/summary")
def summary(session: Session = Depends(get_session)):
    workers = session.exec(select(Worker)).all()
    tasks = session.exec(select(Task)).all()
    now = utcnow()
    online_count = sum(1 for w in workers if normalize_dt(w.last_heartbeat_at) and normalize_dt(w.last_heartbeat_at) >= now - timedelta(seconds=30))
    return {
        "workers": len(workers),
        "workers_online": online_count,
        "tasks_total": len(tasks),
        "tasks_running": sum(1 for t in tasks if t.status in {"assigned", "running"}),
        "tasks_failed": sum(1 for t in tasks if t.status == "failed"),
        "tasks_manual_needed": sum(1 for t in tasks if t.status == "manual_needed"),
    }
