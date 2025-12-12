from datetime import date as date_cls
from typing import List, Optional

from sqlalchemy.orm import Session
from model.task import Task


def create_task(
    db: Session,
    *,
    event_name: str,
    event_description: Optional[str],
    date: date_cls,
    priority: str,
) -> Task:
    task = Task(
        event_name=event_name,
        event_description=event_description or "",
        date=date,
        priority=priority,
        is_active=True,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Optional[Task]:
    return db.query(Task).filter(Task.id == task_id, Task.is_active == True).first()  # noqa: E712


def list_tasks(
    db: Session,
    *,
    for_date: Optional[date_cls] = None,
    include_inactive: bool = False,
) -> List[Task]:
    q = db.query(Task)
    if not include_inactive:
        q = q.filter(Task.is_active == True)  # noqa: E712
    if for_date is not None:
        q = q.filter(Task.date == for_date)
    return q.order_by(Task.date.asc(), Task.id.asc()).all()


def update_task(
    db: Session,
    task_id: int,
    *,
    event_name: Optional[str] = None,
    event_description: Optional[str] = None,
    date: Optional[date_cls] = None,
    priority: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[Task]:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None

    if event_name is not None:
        task.event_name = event_name
    if event_description is not None:
        task.event_description = event_description
    if date is not None:
        task.date = date
    if priority is not None:
        task.priority = priority
    if is_active is not None:
        task.is_active = is_active

    db.commit()
    db.refresh(task)
    return task


def soft_delete_task(db: Session, task_id: int) -> bool:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return False
    task.is_active = False
    db.commit()
    return True

