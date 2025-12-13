from datetime import date as date_cls
from typing import List, Optional

from sqlalchemy.orm import Session

from model.task import Task
from utils.ai_priority import compute_ai_priority_score


def create_task(
    db: Session,
    *,
    event_name: str,
    event_description: Optional[str],
    date: date_cls,
    priority: str,
    due_date: Optional[date_cls] = None,
    username: Optional[str] = None,
) -> Task:
    """
    Create a new task and compute an AI priority score.
    """
    ai_score = compute_ai_priority_score(event_name, event_description or "")

    task = Task(
        event_name=event_name,
        event_description=event_description or "",
        date=date,
        due_date=due_date,
        priority=priority,
        is_active=True,
        username=username,
        ai_priority_score=ai_score,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Optional[Task]:
    return (
        db.query(Task)
        .filter(Task.id == task_id, Task.is_active == True)  # noqa: E712
        .first()
    )


def list_tasks(
    db: Session,
    *,
    for_date: Optional[date_cls] = None,
    username: Optional[str] = None,
    include_inactive: bool = False,
) -> List[Task]:
    """
    List tasks for a given date (and optionally user), used by the calendar view.
    """
    q = db.query(Task)
    if not include_inactive:
        q = q.filter(Task.is_active == True)  # noqa: E712
    if for_date is not None:
        q = q.filter(Task.date == for_date)
    if username is not None:
        q = q.filter(Task.username == username)
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
    due_date: Optional[date_cls] = None,
) -> Optional[Task]:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None

    recompute_ai = False

    if event_name is not None:
        task.event_name = event_name
        recompute_ai = True
    if event_description is not None:
        task.event_description = event_description
        recompute_ai = True
    if date is not None:
        task.date = date
    if due_date is not None:
        task.due_date = due_date
    if priority is not None:
        task.priority = priority
    if is_active is not None:
        task.is_active = is_active

    if recompute_ai:
        task.ai_priority_score = compute_ai_priority_score(
            task.event_name, task.event_description or ""
        )

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


PRIORITY_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}


def list_tasks_by_priority(
    db: Session,
    *,
    username: Optional[str] = None,
    include_inactive: bool = False,
) -> List[Task]:
    """
    List tasks sorted by:
      1. user-assigned priority (High > Medium > Low)
      2. due date (earlier first)
      3. AI semantic score (higher first)
    """
    q = db.query(Task)
    if not include_inactive:
        q = q.filter(Task.is_active == True)  # noqa: E712
    if username is not None:
        q = q.filter(Task.username == username)

    tasks = q.all()

    def sort_key(t: Task):
        user_weight = PRIORITY_WEIGHT.get((t.priority or "Medium").title(), 2)
        due = t.due_date or date_cls.max
        ai_score = float(t.ai_priority_score or 0.0)
        return (-user_weight, due, -ai_score, t.id)

    return sorted(tasks, key=sort_key)

