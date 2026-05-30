from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.models import HeartbeatEvent, Task, TaskEvent, Worker

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="/mnt/c/Users/hp/multi-agent-manager/app/templates")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@router.get("/")
def home():
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard")
def dashboard(request: Request, session: Session = Depends(get_session)):
    workers = session.exec(select(Worker).order_by(Worker.updated_at.desc())).all()
    tasks = session.exec(select(Task).order_by(Task.created_at.desc())).all()
    now = utcnow()
    workers_view = []
    for worker in workers:
        is_online = normalize_dt(worker.last_heartbeat_at) and normalize_dt(worker.last_heartbeat_at) >= now - timedelta(seconds=90)
        workers_view.append({
            "worker": worker,
            "connectivity": "online" if is_online else "offline",
            "state": "needs_attention" if worker.requires_manual_intervention else (worker.status if is_online else "offline"),
        })
    context = {
        "request": request,
        "workers": workers_view,
        "tasks": tasks[:10],
        "stats": {
            "workers_total": len(workers),
            "workers_online": sum(1 for item in workers_view if item["connectivity"] == "online"),
            "workers_needs_attention": sum(1 for item in workers_view if item["worker"].requires_manual_intervention),
            "tasks_running": sum(1 for task in tasks if task.status in {"assigned", "running"}),
        },
    }
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/workers")
def workers_page(request: Request, session: Session = Depends(get_session)):
    workers = session.exec(select(Worker).order_by(Worker.updated_at.desc())).all()
    now = utcnow()
    worker_rows = []
    for worker in workers:
        is_online = normalize_dt(worker.last_heartbeat_at) and normalize_dt(worker.last_heartbeat_at) >= now - timedelta(seconds=90)
        worker_rows.append({
            "worker": worker,
            "connectivity": "online" if is_online else "offline",
            "state": "needs_attention" if worker.requires_manual_intervention else (worker.status if is_online else "offline"),
        })
    return templates.TemplateResponse("workers.html", {"request": request, "workers": worker_rows})


@router.get("/tasks")
def tasks_page(request: Request, session: Session = Depends(get_session)):
    tasks = session.exec(select(Task).order_by(Task.created_at.desc())).all()
    return templates.TemplateResponse("tasks.html", {"request": request, "tasks": tasks})


@router.get("/workers/{worker_id}")
def worker_detail(request: Request, worker_id: str, session: Session = Depends(get_session)):
    worker = session.exec(select(Worker).where(Worker.worker_id == worker_id)).first()
    events = session.exec(select(HeartbeatEvent).where(HeartbeatEvent.worker_id == worker_id).order_by(HeartbeatEvent.created_at.desc())).all()
    return templates.TemplateResponse("worker_detail.html", {"request": request, "worker": worker, "events": events[:50]})


@router.get("/tasks/{task_id}")
def task_detail(request: Request, task_id: str, session: Session = Depends(get_session)):
    task = session.exec(select(Task).where(Task.task_id == task_id)).first()
    events = session.exec(select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.created_at.desc())).all()
    return templates.TemplateResponse("task_detail.html", {"request": request, "task": task, "events": events})
